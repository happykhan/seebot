"""Native Python lint, security, and supporting source observations."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from seebot.analyzers.native import _run_native
from seebot.models import CheckResult, Status
from seebot.runtime.analyzers import AnalyzerEnvironment


def _denominator(files: list[Path]) -> tuple[int, int]:
    lines = sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for path in files
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
    )
    return len(files), lines


def _density(count: int, lines: int) -> float | None:
    return round(1000 * count / lines, 3) if lines else None


def _ruff_parser(
    files: int, lines: int
) -> Callable[[str, str, int], tuple[dict[str, Any], Status]]:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        rows = json.loads(stdout or "[]")
        counts = Counter(str(row.get("code") or "UNKNOWN") for row in rows)
        return (
            {
                "language": "python",
                "analyzer": "ruff",
                "production_files": files,
                "production_nonblank_noncomment_lines": lines,
                "finding_count": len(rows),
                "findings_per_kloc": _density(len(rows), lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_category": rule.rstrip("0123456789") or "UNKNOWN",
                        "native_severity": "UNSPECIFIED",
                        "count": count,
                        "findings_per_kloc": _density(count, lines),
                    }
                    for rule, count in sorted(counts.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _pylint_parser(
    files: int, lines: int
) -> Callable[[str, str, int], tuple[dict[str, Any], Status]]:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        rows = json.loads(stdout or "[]")
        keys = Counter(
            (str(row.get("symbol") or "UNKNOWN"), str(row.get("type") or "UNKNOWN")) for row in rows
        )
        return (
            {
                "language": "python",
                "analyzer": "pylint",
                "production_files": files,
                "production_nonblank_noncomment_lines": lines,
                "finding_count": len(rows),
                "findings_per_kloc": _density(len(rows), lines),
                "rules": [
                    {
                        "rule": symbol,
                        "native_category": category,
                        "native_severity": category,
                        "count": count,
                        "findings_per_kloc": _density(count, lines),
                    }
                    for (symbol, category), count in sorted(keys.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _bandit_parser(
    files: int, lines: int
) -> Callable[[str, str, int], tuple[dict[str, Any], Status]]:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        payload = json.loads(stdout or "{}")
        rows = payload.get("results", [])
        keys = Counter(
            (
                str(row.get("test_id") or "UNKNOWN"),
                str(row.get("issue_severity") or "UNKNOWN"),
                str(row.get("issue_confidence") or "UNKNOWN"),
            )
            for row in rows
        )
        return (
            {
                "language": "python",
                "analyzer": "bandit",
                "production_files": files,
                "production_nonblank_noncomment_lines": lines,
                "finding_count": len(rows),
                "findings_per_kloc": _density(len(rows), lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_severity": severity,
                        "native_confidence": confidence,
                        "count": count,
                        "findings_per_kloc": _density(count, lines),
                    }
                    for (rule, severity, confidence), count in sorted(keys.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _vulture_parser(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
    rows = [line for line in stdout.splitlines() if line.strip()]
    return (
        {
            "language": "python",
            "analyzer": "vulture",
            "candidate_count": len(rows),
            "notes": "Candidates are indicators, not confirmed dead code.",
        },
        Status.OBSERVED,
    )


def run_python_analyzers(
    *,
    environment: AnalyzerEnvironment,
    checkout: Path,
    files: list[Path],
    project_id: str,
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    force: bool = False,
    snapshot_date: str = "2026-07-01",
    snapshot_commit: str | None = None,
) -> list[CheckResult]:
    file_count, lines = _denominator(files)
    relative = [f"/source/{path.relative_to(checkout).as_posix()}" for path in files]
    specs = [
        (
            "SRC-NATIVE-LINT-001",
            "python:ruff",
            [
                "ruff",
                "check",
                "--no-cache",
                "--output-format=json",
                "--config",
                "/config/ruff-standard.toml",
                *relative,
            ],
            _ruff_parser(file_count, lines),
            {0, 1},
        ),
        (
            "SRC-NATIVE-LINT-001",
            "python:pylint",
            [
                "pylint",
                "--output-format=json",
                "--rcfile",
                "/config/pylint-standard.toml",
                *relative,
            ],
            _pylint_parser(file_count, lines),
            set(range(32)),
        ),
        (
            "SRC-NATIVE-SECURITY-001",
            "python:bandit",
            ["bandit", "-q", "-f", "json", *relative],
            _bandit_parser(file_count, lines),
            {0, 1},
        ),
        (
            "SRC-DEAD-CODE-001",
            "python:vulture",
            ["vulture", "--min-confidence", "60", *relative],
            _vulture_parser,
            {0, 1, 3},
        ),
    ]
    return [
        _run_native(
            environment=environment,
            checkout=checkout,
            project_id=project_id,
            snapshot_date=snapshot_date,
            snapshot_commit=snapshot_commit,
            language="python",
            run_id=run_id,
            evidence_root=evidence_root,
            config_root=config_root,
            force=force,
            check_id=check_id,
            probe_id=probe_id,
            command=command,
            parser=parser,
            accepted=accepted,
        )
        for check_id, probe_id, command, parser, accepted in specs
    ]
