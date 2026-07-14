"""Conservative command-backed source measurements shared by language adapters."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot.evidence import audit_code_identity, environment_id, evidence_path, sha256_file
from seebot.models import CheckResult, EvidencePaths, ResultKind, Status, ToolIdentity

Parser = Callable[[str, str, int], dict[str, Any]]


@dataclass(frozen=True)
class CommandMeasurement:
    check_id: str
    domain: str
    tool: str
    command: list[str]
    parser: Parser
    accepted_exit_codes: set[int] = field(default_factory=lambda: {0})
    cwd: Path | None = None
    timeout_seconds: int = 300
    version_command: list[str] | None = None
    stdin_text: str | None = None
    untestable_reason: str | None = None


def tool_version(spec: CommandMeasurement) -> str:
    command = spec.version_command or [spec.tool, "--version"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else "UNKNOWN"


def run_measurements(
    specs: list[CommandMeasurement],
    *,
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    language: str,
    source_roots: list[Path],
    force: bool = False,
) -> list[CheckResult]:
    """Run measurements, preserving missing prerequisites as UNTESTABLE."""
    results: list[CheckResult] = []
    for spec in specs:
        check_dir = evidence_root / run_id / package_id / spec.check_id
        result_path = check_dir / "result.json"
        if result_path.exists() and not force:
            results.append(CheckResult.model_validate_json(result_path.read_text(encoding="utf-8")))
            continue
        check_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now(UTC)
        clock = time.monotonic()
        stdout = ""
        stderr = ""
        observed: dict[str, Any] = {
            "language": language,
            "source_roots": [root.as_posix() for root in source_roots],
        }
        notes: str | None = None
        status = Status.ERROR
        executable = shutil.which(spec.command[0])
        if spec.untestable_reason:
            status = Status.UNTESTABLE
            observed["missing_prerequisite"] = spec.untestable_reason
            notes = (
                "Required analysis prerequisite is unavailable; no package judgement was inferred."
            )
        elif executable is None:
            status = Status.UNTESTABLE
            observed["missing_executable"] = spec.command[0]
            notes = "Required pinned analyzer is unavailable; no package judgement was inferred."
        else:
            try:
                completed = subprocess.run(
                    spec.command,
                    cwd=spec.cwd,
                    capture_output=True,
                    text=True,
                    input=spec.stdin_text,
                    check=False,
                    timeout=spec.timeout_seconds,
                )
                stdout, stderr = completed.stdout, completed.stderr
                observed |= spec.parser(stdout, stderr, completed.returncode)
                observed["tool_exit_code"] = completed.returncode
                parser_status = observed.pop("_audit_status", None)
                if parser_status == "UNTESTABLE":
                    status = Status.UNTESTABLE
                    notes = (
                        "Analyzer prerequisite is unavailable; no package judgement was inferred."
                    )
                elif completed.returncode in spec.accepted_exit_codes:
                    status = Status.PASS
                else:
                    status = Status.ERROR
                    notes = "Analyzer command failed; no package judgement was inferred."
            except subprocess.TimeoutExpired as exc:
                raw_stdout = exc.stdout or ""
                raw_stderr = exc.stderr or ""
                stdout = (
                    raw_stdout.decode(errors="replace")
                    if isinstance(raw_stdout, bytes)
                    else raw_stdout
                )
                stderr = (
                    raw_stderr.decode(errors="replace")
                    if isinstance(raw_stderr, bytes)
                    else raw_stderr
                )
                status = Status.ERROR
                observed["timed_out"] = True
                notes = "Analyzer timed out; no package judgement was inferred."
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                stderr = f"{type(exc).__name__}: {exc}\n"
                observed["audit_error"] = type(exc).__name__
                notes = "Analyzer machinery failed; no package judgement was inferred."
        duration = time.monotonic() - clock
        stdout_path, stderr_path = check_dir / "stdout.txt", check_dir / "stderr.txt"
        metadata_path = check_dir / "metadata.json"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        version = tool_version(spec) if executable else "UNAVAILABLE"
        metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "command": spec.command,
                    "working_directory": str(spec.cwd),
                    "started_at": started.isoformat().replace("+00:00", "Z"),
                    "duration_seconds": duration,
                    "environment_id": environment_id(),
                    "tool": {"name": spec.tool, "version": version},
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
            check_id=spec.check_id,
            domain=spec.domain,
            status=status,
            result_kind=ResultKind.MEASUREMENT,
            method="automated",
            expected={"measurement_only": True},
            observed=observed,
            tool=ToolIdentity(name=spec.tool, version=version),
            command=spec.command,
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


def line_count_parser(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    return {"output_line_count": len([line for line in (stdout + stderr).splitlines() if line])}
