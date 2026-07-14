"""Production-source Python observations without quality-score interpretation."""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot.evidence import (
    audit_code_identity,
    environment_id,
    evidence_path,
    sha256_file,
)
from seebot.models import CheckResult, EvidencePaths, ResultKind, Status, ToolIdentity

Parser = Callable[[str], dict[str, Any]]


def _ruff(stdout: str) -> dict[str, Any]:
    rows = json.loads(stdout or "[]")
    codes = Counter(row.get("code") or "UNKNOWN" for row in rows)
    return {"finding_count": len(rows), "findings_by_code": dict(sorted(codes.items()))}


def _pylint(stdout: str) -> dict[str, Any]:
    rows = json.loads(stdout or "[]")
    symbols = Counter(row.get("symbol") or "UNKNOWN" for row in rows)
    categories = Counter(row.get("type") or "UNKNOWN" for row in rows)
    return {
        "message_count": len(rows),
        "messages_by_category": dict(sorted(categories.items())),
        "messages_by_symbol": dict(sorted(symbols.items())),
    }


def _radon(stdout: str) -> dict[str, Any]:
    files = json.loads(stdout or "{}")
    blocks = [block for file_blocks in files.values() for block in file_blocks]
    grades = Counter(block.get("rank") or "UNKNOWN" for block in blocks)
    complexities = [int(block["complexity"]) for block in blocks if "complexity" in block]
    return {
        "block_count": len(blocks),
        "complexity_mean": sum(complexities) / len(complexities) if complexities else None,
        "complexity_max": max(complexities) if complexities else None,
        "blocks_by_grade": dict(sorted(grades.items())),
    }


def _interrogate(stdout: str) -> dict[str, Any]:
    percentages = re.findall(r"(\d+(?:\.\d+)?)%", stdout)
    return {"docstring_coverage_percent": float(percentages[-1]) if percentages else None}


def _vulture(stdout: str) -> dict[str, Any]:
    rows = [line for line in stdout.splitlines() if line.strip()]
    confidences: Counter[str] = Counter()
    for row in rows:
        match = re.search(r"(\d+)% confidence", row)
        confidences[match.group(1) if match else "UNKNOWN"] += 1
    return {"candidate_count": len(rows), "candidates_by_confidence": dict(confidences)}


def _bandit(stdout: str) -> dict[str, Any]:
    report = json.loads(stdout or "{}")
    issues = report.get("results", [])
    severities = Counter(issue.get("issue_severity") or "UNKNOWN" for issue in issues)
    confidences = Counter(issue.get("issue_confidence") or "UNKNOWN" for issue in issues)
    return {
        "indicator_count": len(issues),
        "indicators_by_severity": dict(sorted(severities.items())),
        "indicators_by_confidence": dict(sorted(confidences.items())),
    }


def _tool_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, check=False
    )
    return (completed.stdout or completed.stderr).strip().splitlines()[0]


def _source_denominator(source_roots: list[Path]) -> dict[str, int]:
    files = sorted({path for root in source_roots for path in root.rglob("*.py")})
    lines = 0
    for path in files:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines += 1
    return {"python_files": len(files), "nonblank_noncomment_lines": lines}


def run_python_analyzers(
    *,
    source_roots: list[Path],
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    manifest_sha256: str,
    force: bool = False,
) -> list[CheckResult]:
    """Run the fixed pilot toolchain and retain each tool's unmodified output."""
    denominator = _source_denominator(source_roots)
    try:
        command_source_roots = [root.relative_to(Path.cwd()) for root in source_roots]
        command_config_root = config_root.relative_to(Path.cwd())
    except ValueError:
        command_source_roots = source_roots
        command_config_root = config_root
    source_arguments = [str(path) for path in command_source_roots]
    specs: list[tuple[str, str, list[str], set[int], Path, Parser]] = [
        (
            "PY-RUFF-001",
            "ruff",
            [
                "ruff",
                "check",
                "--output-format=json",
                "--config",
                str(command_config_root / "ruff-standard.toml"),
                *source_arguments,
            ],
            {0, 1},
            config_root / "ruff-standard.toml",
            _ruff,
        ),
        (
            "PY-PYLINT-001",
            "pylint",
            [
                "pylint",
                "--output-format=json",
                "--recursive=y",
                "--rcfile",
                str(command_config_root / "pylint-standard.toml"),
                *source_arguments,
            ],
            set(range(32)),
            config_root / "pylint-standard.toml",
            _pylint,
        ),
        (
            "PY-RADON-001",
            "radon",
            ["radon", "cc", "-j", "-s", *source_arguments],
            {0},
            config_root / "audit.yaml",
            _radon,
        ),
        (
            "PY-INTERROGATE-001",
            "interrogate",
            [
                "interrogate",
                "-vv",
                "--no-color",
                "--fail-under",
                "0",
                "-c",
                str(command_config_root / "interrogate-standard.toml"),
                *source_arguments,
            ],
            {0},
            config_root / "interrogate-standard.toml",
            _interrogate,
        ),
        (
            "PY-VULTURE-001",
            "vulture",
            ["vulture", "--min-confidence", "60", *source_arguments],
            {0, 1, 3},
            config_root / "audit.yaml",
            _vulture,
        ),
        (
            "PY-BANDIT-001",
            "bandit",
            ["bandit", "-r", "-q", "-f", "json", *source_arguments],
            {0, 1},
            config_root / "audit.yaml",
            _bandit,
        ),
    ]
    results: list[CheckResult] = []
    for check_id, tool_name, command, measurement_codes, config_path, parser in specs:
        check_dir = evidence_root / run_id / package_id / check_id
        result_path = check_dir / "result.json"
        if result_path.exists() and not force:
            results.append(CheckResult.model_validate_json(result_path.read_text(encoding="utf-8")))
            continue
        check_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now(UTC)
        clock = time.monotonic()
        status = Status.ERROR
        notes: str | None = None
        observed: dict[str, Any] = {}
        stdout = ""
        stderr = ""
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            stdout, stderr = completed.stdout, completed.stderr
            if completed.returncode in measurement_codes:
                parser_input = stdout if stdout.strip() else stderr
                observed = (
                    parser(parser_input) | denominator | {"tool_exit_code": completed.returncode}
                )
                status = Status.PASS
            else:
                observed = {"tool_exit_code": completed.returncode}
                notes = "Static-analysis tool failed; no package judgement was inferred."
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            stderr = f"{type(exc).__name__}: {exc}\n"
            observed = {"audit_error": type(exc).__name__}
            notes = "Static-analysis machinery failed; no package judgement was inferred."
        duration = time.monotonic() - clock
        stdout_path = check_dir / "stdout.txt"
        stderr_path = check_dir / "stderr.txt"
        metadata_path = check_dir / "metadata.json"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "command": command,
                    "source_roots": [path.as_posix() for path in command_source_roots],
                    "started_at": started.isoformat().replace("+00:00", "Z"),
                    "duration_seconds": duration,
                    "environment_id": environment_id(),
                    "tool": {"name": tool_name, "version": _tool_version(tool_name)},
                    "manifest_sha256": manifest_sha256,
                    **audit_code_identity(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = CheckResult(
            run_id=run_id,
            package_id=package_id,
            check_id=check_id,
            domain="python",
            status=status,
            result_kind=ResultKind.MEASUREMENT,
            method="automated",
            expected={"measurement_only": True},
            observed=observed,
            tool=ToolIdentity(name=tool_name, version=_tool_version(tool_name)),
            command=command,
            started_at=started,
            duration_seconds=duration,
            environment_id=environment_id(),
            config_sha256=sha256_file(config_path),
            evidence=EvidencePaths(
                stdout=evidence_path(stdout_path, evidence_root),
                stderr=evidence_path(stderr_path, evidence_root),
                metadata=evidence_path(metadata_path, evidence_root),
            ),
            notes=notes,
        )
        result.write(result_path)
        results.append(result)
    return results
