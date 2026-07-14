"""Evidence capture that distinguishes tool outcomes from audit errors."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bioconda_audit import __version__
from bioconda_audit.models import (
    CheckResult,
    EvidencePaths,
    Status,
    ToolIdentity,
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def environment_id() -> str:
    identity = {
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
    }
    return "sha256:" + sha256_bytes(json.dumps(identity, sort_keys=True).encode())


@dataclass(frozen=True)
class ProbeSpec:
    package_id: str
    check_id: str
    command: list[str]
    allowed_exit_codes: list[int]
    timeout_seconds: int


def run_probe(
    spec: ProbeSpec,
    *,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    force: bool = False,
) -> CheckResult:
    """Run one command and atomically preserve its raw evidence.

    Failure to start or supervise a command is ERROR. A successfully supervised
    command whose exit code violates the declared contract is FAIL.
    """
    check_dir = evidence_root / run_id / spec.package_id / spec.check_id
    result_path = check_dir / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))

    check_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = check_dir / "stdout.txt"
    stderr_path = check_dir / "stderr.txt"
    metadata_path = check_dir / "metadata.json"
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    observed: dict[str, object] = {}
    notes: str | None = None

    clean_env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH"}}
    try:
        completed = subprocess.run(
            spec.command,
            cwd=check_dir,
            env=clean_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=spec.timeout_seconds,
            check=False,
        )
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        observed = {"exit_code": completed.returncode, "timed_out": False}
        status = Status.PASS if completed.returncode in spec.allowed_exit_codes else Status.FAIL
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_bytes(exc.stdout or b"")
        stderr_path.write_bytes(exc.stderr or b"")
        observed = {"exit_code": None, "timed_out": True}
        status = Status.FAIL
        notes = "Command exceeded the declared interface timeout."
    except OSError as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(exc) + "\n", encoding="utf-8")
        observed = {"exit_code": None, "audit_error": type(exc).__name__}
        notes = "Audit machinery could not start the command."

    duration = time.monotonic() - clock
    env_id = environment_id()
    metadata = {
        "schema_version": 1,
        "command": spec.command,
        "working_directory_policy": "empty per-check evidence directory",
        "working_directory": str(check_dir),
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "duration_seconds": duration,
        "environment_id": env_id,
        "tool": {"name": "bcqa", "version": __version__},
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    result = CheckResult(
        run_id=run_id,
        package_id=spec.package_id,
        check_id=spec.check_id,
        domain="cli",
        status=status,
        expected={"exit_codes": spec.allowed_exit_codes, "timeout_seconds": spec.timeout_seconds},
        observed=observed,
        tool=ToolIdentity(name="bcqa", version=__version__),
        command=spec.command,
        started_at=started,
        duration_seconds=duration,
        environment_id=env_id,
        config_sha256=sha256_file(config_path),
        evidence=EvidencePaths(
            stdout=str(stdout_path), stderr=str(stderr_path), metadata=str(metadata_path)
        ),
        notes=notes,
    )
    result.write(result_path)
    return result
