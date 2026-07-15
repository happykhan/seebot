"""Pixi-first native pilot environments with explicit solved-build provenance."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot import __version__
from seebot.evidence import audit_code_identity, evidence_path, sha256_file
from seebot.models import CheckResult, EvidencePaths, Status, ToolIdentity


def pixi_executable() -> Path:
    discovered = shutil.which("pixi")
    fallback = Path.home() / ".pixi" / "bin" / "pixi"
    candidate = Path(discovered) if discovered else fallback
    if not candidate.is_file():
        raise FileNotFoundError("Pixi is required: https://pixi.sh")
    return candidate


@dataclass(frozen=True)
class PixiEnvironment:
    manifest_path: Path
    lock_path: Path
    platform: str
    package_record: dict[str, Any]
    pixi_version: str

    @property
    def environment_id(self) -> str:
        return f"pixi-lock:sha256:{sha256_file(self.lock_path)}"


@dataclass(frozen=True)
class PixiProbeSpec:
    package_id: str
    check_id: str
    domain: str
    command: list[str]
    allowed_exit_codes: list[int]
    timeout_seconds: int
    environment: PixiEnvironment
    fixture_directory: Path | None = None
    expected_stdout_contains: str | None = None
    expected_output_sha256: dict[str, str] | None = None
    manifest_sha256: str | None = None
    repeat_count: int = 1
    required_text_tokens: tuple[str, ...] = ()
    required_any_text_tokens: tuple[str, ...] = ()
    forbid_traceback: bool = False
    require_diagnostic: bool = False
    forbid_created_files: bool = False


def _run_json(command: list[str]) -> Any:
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def prepare_environment(
    root: Path,
    *,
    package_name: str,
    version: str,
    channels: list[str],
) -> PixiEnvironment:
    """Create or reuse a native Pixi environment for one reviewed package version."""
    pixi = pixi_executable()
    info = _run_json([str(pixi), "info", "--json"])
    platform_name = str(info["platform"])
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "pixi.toml"
    lock_path = root / "pixi.lock"
    channel_text = ", ".join(json.dumps(value) for value in channels)
    manifest_text = (
        "[workspace]\n"
        f'name = "seebot-{package_name}"\n'
        f"channels = [{channel_text}]\n"
        f'platforms = ["{platform_name}"]\n\n'
        "[dependencies]\n"
        f'{json.dumps(package_name)} = "=={version}"\n'
    )
    changed = (
        not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != manifest_text
    )
    if changed:
        manifest_path.write_text(manifest_text, encoding="utf-8")
        lock_path.unlink(missing_ok=True)
    install = [str(pixi), "install", "--manifest-path", str(manifest_path)]
    if lock_path.exists() and not changed:
        install.append("--locked")
    subprocess.run(install, capture_output=True, text=True, check=True)
    records = _run_json([str(pixi), "list", "--manifest-path", str(manifest_path), "--json"])
    package_record = next(
        (record for record in records if record.get("name") == package_name), None
    )
    if package_record is None:
        raise RuntimeError(f"Pixi environment does not contain {package_name}")
    version_output = subprocess.run(
        [str(pixi), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return PixiEnvironment(
        manifest_path=manifest_path,
        lock_path=lock_path,
        platform=platform_name,
        package_record=package_record,
        pixi_version=version_output,
    )


def _native_command(spec: PixiProbeSpec, check_dir: Path) -> list[str]:
    resolved: list[str] = []
    for value in spec.command:
        if value == "/work":
            resolved.append(str(check_dir))
        elif value.startswith("/work/"):
            resolved.append(str(check_dir / value.removeprefix("/work/")))
        elif value == "/fixtures" and spec.fixture_directory:
            resolved.append(str(spec.fixture_directory))
        elif value.startswith("/fixtures/") and spec.fixture_directory:
            resolved.append(str(spec.fixture_directory / value.removeprefix("/fixtures/")))
        else:
            resolved.append(value)
    return resolved


def run_pixi_probe(
    spec: PixiProbeSpec,
    *,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    force: bool = False,
) -> CheckResult:
    """Execute a probe in a locked native Pixi environment and preserve evidence."""
    check_dir = evidence_root / run_id / spec.package_id / spec.check_id
    result_path = check_dir / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    check_dir.mkdir(parents=True, exist_ok=True)
    for output_name in spec.expected_output_sha256 or {}:
        (check_dir / output_name).unlink(missing_ok=True)
    pixi = pixi_executable()
    audited_command = _native_command(spec, check_dir)
    runner_command = [
        str(pixi),
        "run",
        "--manifest-path",
        str(spec.environment.manifest_path),
        "--",
        *audited_command,
    ]
    stdout_path = check_dir / "stdout.txt"
    stderr_path = check_dir / "stderr.txt"
    metadata_path = check_dir / "metadata.json"
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    observed: dict[str, Any] = {}
    notes: str | None = None
    clean_env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    try:
        before_files = {
            path.relative_to(check_dir).as_posix()
            for path in check_dir.rglob("*")
            if path.is_file()
        }
        completed = subprocess.run(
            runner_command,
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
        combined_text = (completed.stdout + completed.stderr).decode(errors="replace")
        observed["traceback_detected"] = "Traceback (most recent call last)" in combined_text
        observed["usage_or_help_text_detected"] = any(
            token in combined_text.lower() for token in ("usage", "options", "help")
        )
        after_files = {
            path.relative_to(check_dir).as_posix()
            for path in check_dir.rglob("*")
            if path.is_file()
            and path.name not in {"stdout.txt", "stderr.txt", "metadata.json", "result.json"}
        }
        observed["files_created"] = sorted(after_files - before_files)
        lowered_text = combined_text.lower()
        if spec.required_text_tokens:
            matched = all(token.lower() in lowered_text for token in spec.required_text_tokens)
            observed["required_text_detected"] = matched
            if status is Status.PASS and not matched:
                status = Status.FAIL
        if spec.required_any_text_tokens:
            matched = any(token.lower() in lowered_text for token in spec.required_any_text_tokens)
            observed["interface_detail_detected"] = matched
            if status is Status.PASS and not matched:
                status = Status.FAIL
        if spec.forbid_traceback and observed["traceback_detected"]:
            status = Status.FAIL
        if spec.require_diagnostic:
            observed["diagnostic_text_detected"] = bool(combined_text.strip())
            if status is Status.PASS and not observed["diagnostic_text_detected"]:
                status = Status.FAIL
        if spec.forbid_created_files and observed["files_created"]:
            status = Status.FAIL
        if spec.repeat_count > 1:
            repeated = subprocess.run(
                runner_command,
                cwd=check_dir,
                env=clean_env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=spec.timeout_seconds,
                check=False,
            )
            observed["repeat_count"] = spec.repeat_count
            observed["repeatable_exit_code"] = repeated.returncode == completed.returncode
            observed["repeatable_stdout"] = repeated.stdout == completed.stdout
            observed["repeatable_stderr"] = repeated.stderr == completed.stderr
        decoded_stdout = completed.stdout.decode(errors="replace")
        if spec.expected_stdout_contains:
            matched = spec.expected_stdout_contains in decoded_stdout
            observed["stdout_contains_expected"] = matched
            if status is Status.PASS and not matched:
                status = Status.FAIL
        output_hashes: dict[str, str | None] = {}
        for output_name, expected_hash in (spec.expected_output_sha256 or {}).items():
            output_path = check_dir / output_name
            actual_hash = sha256_file(output_path) if output_path.is_file() else None
            output_hashes[output_name] = actual_hash
            if actual_hash != expected_hash:
                status = Status.FAIL
        if output_hashes:
            observed["output_sha256"] = output_hashes
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_bytes(exc.stdout or b"")
        stderr_path.write_bytes(exc.stderr or b"")
        observed = {"exit_code": None, "timed_out": True}
        status = Status.FAIL
        notes = "Command exceeded the declared interface timeout."
    except OSError as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        observed = {"exit_code": None, "audit_error": type(exc).__name__}
        notes = "Audit machinery could not start Pixi."
    duration = time.monotonic() - clock
    package_record = spec.environment.package_record
    metadata = {
        "schema_version": 1,
        "command": spec.command,
        "resolved_command": audited_command,
        "runner_command": runner_command,
        "working_directory_policy": "empty per-check native directory",
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "duration_seconds": duration,
        "environment_id": spec.environment.environment_id,
        "network_isolation": False,
        "pixi": {
            "version": spec.environment.pixi_version,
            "platform": spec.environment.platform,
            "lock_sha256": sha256_file(spec.environment.lock_path),
            "package": {
                key: package_record.get(key)
                for key in ("name", "version", "build", "subdir", "sha256", "url")
            },
        },
        "manifest_sha256": spec.manifest_sha256,
        **audit_code_identity(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    result = CheckResult(
        run_id=run_id,
        package_id=spec.package_id,
        check_id=spec.check_id,
        domain=spec.domain,
        status=status,
        expected={
            "exit_codes": spec.allowed_exit_codes,
            "timeout_seconds": spec.timeout_seconds,
            "stdout_contains": spec.expected_stdout_contains,
            "output_sha256": spec.expected_output_sha256 or {},
            "repeat_count": spec.repeat_count,
        },
        observed=observed
        | {
            "resolved_package": {
                key: package_record.get(key) for key in ("name", "version", "build", "subdir")
            }
        },
        tool=ToolIdentity(name="seebot", version=__version__),
        command=spec.command,
        started_at=started,
        duration_seconds=duration,
        environment_id=spec.environment.environment_id,
        config_sha256=sha256_file(config_path),
        evidence=EvidencePaths(
            stdout=evidence_path(stdout_path, evidence_root),
            stderr=evidence_path(stderr_path, evidence_root),
            metadata=evidence_path(metadata_path, evidence_root),
        ),
        notes=notes,
    )
    result.write(result_path)
    return result
