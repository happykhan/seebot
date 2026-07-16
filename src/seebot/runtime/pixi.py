"""Canonical Linux x86-64 Pixi environments and bounded CLI probes."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot import __version__
from seebot.evidence import audit_code_identity, evidence_path, sha256_file
from seebot.models import CheckResult, EvidencePaths, Status, ToolIdentity
from seebot.runtime.container import (
    cleanup_timed_out_container,
    container_command,
    runtime_executable,
    runtime_name,
)
from seebot.runtime.pixi_image import PIXI_IMAGE

PLATFORM = "linux/amd64"
CRASH_PATTERNS = (
    "traceback (most recent call last)",
    "segmentation fault",
    "core dumped",
    "panicked at",
    "fatal runtime error",
    "java.lang.",
)
SPECIFIC_DIAGNOSTIC_PATTERNS = (
    r"no such file",
    r"not found",
    r"does not exist",
    r"cannot open",
    r"unrecogni[sz]ed (?:option|argument)",
    r"unknown (?:option|argument)",
    r"invalid (?:option|argument|value|format|input)",
    r"out of range",
    r"permission denied",
    r"read-only file system",
    r"malformed",
    r"parse error",
    r"unexpected end",
)
EXECUTABLE_LAUNCH_FAILURES = {
    126: ("cannot execute", "permission denied"),
    127: ("command not found",),
}


def docker_executable() -> str:
    """Compatibility accessor retained for callers that explicitly require Docker."""
    executable = shutil.which("docker")
    if executable is None:
        raise FileNotFoundError("Docker is not available")
    return executable


@dataclass(frozen=True)
class PixiEnvironment:
    project_id: str
    installation_id: str
    root: Path
    manifest_path: Path
    lock_path: Path
    package_record: dict[str, Any]
    package_records: tuple[dict[str, Any], ...] = ()
    image: str = PIXI_IMAGE
    platform: str = PLATFORM
    pixi_version: str = "pixi 0.72.2"
    compatibility_adjustments: tuple[str, ...] = ()

    @property
    def environment_id(self) -> str:
        if runtime_name() == "native":
            runtime = f"native-pixi:{sha256_file(Path(runtime_executable()))}"
        else:
            runtime = f"image:{self.image.rsplit('@', 1)[-1]}"
        adjustment = ";case-aliases:pruned" if self.compatibility_adjustments else ""
        return (
            f"pixi-lock:{sha256_file(self.lock_path)};{runtime};"
            f"platform:{self.platform}{adjustment}"
        )


@dataclass(frozen=True)
class ExpectedOutput:
    path: str
    nonempty: bool = True
    parser: str | None = None
    record_count: int | None = None


@dataclass(frozen=True)
class PixiProbeSpec:
    project_id: str
    check_id: str
    probe_id: str
    domain: str
    command: list[str]
    timeout_seconds: int
    environment: PixiEnvironment
    snapshot_date: str = "2026-07-01"
    snapshot_commit: str | None = None
    executable_id: str | None = None
    allowed_exit_codes: tuple[int, ...] = (0,)
    fixture_directory: Path | None = None
    expected_outputs: tuple[ExpectedOutput, ...] = ()
    diagnostic_expectation: str = "not_applicable"
    error_contract: bool = False
    allow_successful_empty_input: bool = False
    required_all_text: tuple[str, ...] = ()
    required_any_text: tuple[str, ...] = ()
    expected_version: str | None = None
    require_stdout_nonempty: bool = False
    stdout_parser: str | None = None
    stdout_record_count: int | None = None
    stdin_fixture: Path | None = None
    manifest_sha256: str | None = None
    environment_variables: dict[str, str] = field(default_factory=dict)


def _run(
    command: list[str], *, timeout: int = 1800, stdin_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL if stdin_bytes is None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=stdin_bytes, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(command, timeout, stdout, stderr) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _repair_case_colliding_aliases(cache_root: Path) -> tuple[str, ...]:
    """Drop identical case-only aliases lost on a case-insensitive host filesystem.

    Some Linux Conda packages publish the same executable bytes as both ``Tool`` and
    ``tool``. A macOS bind mount can retain only one name, so Pixi sees a missing cache
    source while linking. Keeping the lowercase alias preserves the reviewed executable
    and its hash; packages with differing content are never modified.
    """
    adjusted: list[str] = []
    for metadata_path in sorted((cache_root / "pkgs").glob("*/info/paths.json")):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        paths = payload.get("paths")
        if not isinstance(paths, list):
            continue
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in paths:
            if isinstance(row, dict) and isinstance(row.get("_path"), str):
                groups.setdefault(str(row["_path"]).casefold(), []).append(row)
        remove: set[str] = set()
        for group in groups.values():
            if len(group) < 2:
                continue
            hashes = {str(row.get("sha256")) for row in group}
            if len(hashes) != 1:
                continue
            names = [str(row["_path"]) for row in group]
            keep = next((name for name in names if name == name.lower()), sorted(names)[0])
            remove.update(name for name in names if name != keep)
        if not remove:
            continue
        payload["paths"] = [row for row in paths if str(row.get("_path")) not in remove]
        metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        files_path = metadata_path.with_name("files")
        if files_path.exists():
            lines = files_path.read_text(encoding="utf-8").splitlines()
            files_path.write_text(
                "\n".join(line for line in lines if line not in remove) + "\n",
                encoding="utf-8",
            )
        package = metadata_path.parents[1].name
        adjusted.append(f"{package}:removed-identical-aliases:{','.join(sorted(remove))}")
    return tuple(adjusted)


def prepare_environment(
    root: Path,
    *,
    cache_root: Path,
    project_id: str,
    package_name: str,
    version: str,
    build: str | None,
    channels: list[str],
) -> PixiEnvironment:
    """Install one artifact inside the pinned amd64 Pixi image."""
    root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "pixi.toml"
    lock_path = root / "pixi.lock"
    channels_text = ", ".join(json.dumps(channel) for channel in channels)
    manifest_text = (
        "[workspace]\n"
        f'name = "seebot-{project_id}"\n'
        f"channels = [{channels_text}]\n"
        'platforms = ["linux-64"]\n\n'
        "[dependencies]\n"
        f"{json.dumps(package_name)} = "
        + (
            "{ version = " + json.dumps("==" + version) + ", build = " + json.dumps(build) + " }\n"
            if build
            else json.dumps("==" + version) + "\n"
        )
    )
    if not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != manifest_text:
        manifest_path.write_text(manifest_text, encoding="utf-8")
        lock_path.unlink(missing_ok=True)
        shutil.rmtree(root / ".pixi", ignore_errors=True)
    offline = os.environ.get("SEEBOT_OFFLINE") == "1"
    install = container_command(
        [
            "pixi",
            "install",
            "--manifest-path",
            "/workspace/pixi.toml",
        ],
        network="none" if offline else "bridge",
        read_only=False,
        mounts=((root, "/workspace", "rw"), (cache_root, "/cache", "rw")),
        environment={"PIXI_CACHE_DIR": "/cache"},
        workdir="/workspace",
    )
    if lock_path.exists():
        install.append("--locked")
    prepared_prefix = root / ".pixi" / "envs" / "default"
    if offline and (not lock_path.is_file() or not prepared_prefix.is_dir()):
        raise RuntimeError(f"Offline environment is incomplete for {project_id}")
    completed = subprocess.CompletedProcess(install, 0, b"", b"") if offline else _run(install)
    adjustments: tuple[str, ...] = ()
    if completed.returncode != 0:
        adjustments = _repair_case_colliding_aliases(cache_root)
        if adjustments:
            shutil.rmtree(root / ".pixi", ignore_errors=True)
            completed = _run(install)
    if completed.returncode != 0:
        detail = completed.stderr.decode(errors="replace")[-2000:]
        raise RuntimeError(f"Pixi installation failed for {project_id}: {detail}")
    list_command = container_command(
        [
            "pixi",
            "list",
            "--manifest-path",
            "/workspace/pixi.toml",
            "--json",
        ],
        mounts=((root, "/workspace", "rw"),),
        workdir="/workspace",
    )
    listed = _run(list_command, timeout=120)
    if listed.returncode != 0:
        raise RuntimeError(listed.stderr.decode(errors="replace")[-2000:])
    records = json.loads(listed.stdout)
    record = next((row for row in records if row.get("name") == package_name), None)
    if record is None:
        raise RuntimeError(f"Installed environment does not contain {package_name}")
    if build and record.get("build") != build:
        raise RuntimeError(
            f"Resolved build {record.get('build')} does not match reviewed build {build}"
        )
    return PixiEnvironment(
        project_id=project_id,
        installation_id=f"pixi:{package_name}={record.get('version')}:{record.get('build')}",
        root=root,
        manifest_path=manifest_path,
        lock_path=lock_path,
        package_record=record,
        package_records=tuple(records),
        compatibility_adjustments=adjustments,
    )


def _diagnostic_class(stderr: str, crash_detected: bool) -> str:
    if not stderr.strip():
        return "EMPTY"
    if crash_detected:
        return "INTERNAL"
    if any(re.search(pattern, stderr, re.IGNORECASE) for pattern in SPECIFIC_DIAGNOSTIC_PATTERNS):
        return "SPECIFIC"
    return "GENERIC"


def _executable_launch_failed(exit_code: int, stderr: str) -> bool:
    """Identify shell failures to launch the reviewed executable."""
    lowered = stderr.lower()
    if any(marker in lowered for marker in EXECUTABLE_LAUNCH_FAILURES.get(exit_code, ())):
        return True
    return exit_code != 0 and any(
        marker in lowered for markers in EXECUTABLE_LAUNCH_FAILURES.values() for marker in markers
    )


def _inspect_output(
    path: Path, parser: str | None, *, allow_empty: bool = False
) -> tuple[bool, int | None, str | None]:
    if parser is None:
        return True, None, None
    try:
        text = path.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if line.strip()]
        if parser == "fastq":
            valid = (
                (bool(lines) or allow_empty)
                and len(lines) % 4 == 0
                and all(
                    lines[index].startswith("@")
                    and lines[index + 2].startswith("+")
                    and len(lines[index + 1]) == len(lines[index + 3])
                    for index in range(0, len(lines), 4)
                )
            )
            record_count = len(lines) // 4 if valid else None
        elif parser == "fasta":
            valid = (not lines and allow_empty) or (
                bool(lines)
                and lines[0].startswith(">")
                and any(not line.startswith(">") for line in lines)
            )
            record_count = sum(line.startswith(">") for line in lines) if valid else None
        elif parser == "vcf":
            records = [line for line in lines if not line.startswith("#")]
            valid = any(line.startswith("#CHROM") for line in lines) and all(
                len(line.split("\t")) >= 8 and line.split("\t")[1].isdigit() for line in records
            )
            record_count = len(records) if valid else None
        elif parser == "gff3":
            records = [line for line in lines if not line.startswith("#")]
            valid = (bool(records) or allow_empty) and all(
                len(line.split("\t")) == 9 for line in records
            )
            record_count = len(records) if valid else None
        elif parser == "bed":
            valid = (bool(lines) or allow_empty) and all(
                len(line.split("\t")) >= 3 for line in lines
            )
            record_count = len(lines) if valid else None
        elif parser == "paf":
            valid = (bool(lines) or allow_empty) and all(
                len(line.split("\t")) >= 12 for line in lines
            )
            record_count = len(lines) if valid else None
        elif parser == "tsv":
            valid = (bool(lines) or allow_empty) and all(
                len(line.split("\t")) >= 2 for line in lines
            )
            record_count = len(lines) if valid else None
        elif parser == "sam":
            records = [line for line in lines if not line.startswith("@")]
            valid = (
                any(line.startswith("@HD") for line in lines)
                and (bool(records) or allow_empty)
                and all(
                    len(line.split("\t")) >= 11 and line.split("\t")[3].isdigit()
                    for line in records
                )
            )
            record_count = len(records) if valid else None
        elif parser == "newick":
            valid = text.strip().endswith(";") and text.count("(") == text.count(")")
            record_count = None
        elif parser == "json":
            json.loads(text)
            valid = True
            record_count = None
        elif parser == "text":
            valid = bool(text.strip())
            record_count = None
        else:
            return False, None, f"unknown parser {parser}"
    except (OSError, UnicodeError, json.JSONDecodeError, IndexError) as exc:
        return False, None, f"{type(exc).__name__}: {exc}"
    return valid, record_count, None if valid else f"output did not satisfy {parser} structure"


def _probe_directory(spec: PixiProbeSpec, evidence_root: Path, run_id: str) -> Path:
    executable = re.sub(r"[^a-zA-Z0-9_.-]+", "-", spec.executable_id or "project")
    probe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", spec.probe_id)
    return evidence_root / run_id / spec.project_id / spec.check_id / executable / probe


def run_pixi_probe(
    spec: PixiProbeSpec,
    *,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    force: bool = False,
) -> CheckResult:
    """Run one bounded probe without network and preserve normalized evidence."""
    check_dir = _probe_directory(spec, evidence_root, run_id)
    result_path = check_dir / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    if force:
        shutil.rmtree(check_dir, ignore_errors=True)
    check_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = check_dir / "stdout.txt"
    stderr_path = check_dir / "stderr.txt"
    metadata_path = check_dir / "metadata.json"
    identity = (run_id, spec.project_id, spec.check_id, spec.executable_id)
    container_name = f"seebot-{abs(hash(identity)) & 0xFFFFFFFF:x}"
    mounts: list[tuple[Path, str, str]] = [
        (spec.environment.root, "/workspace", "rw"),
        (check_dir, "/work", "rw"),
    ]
    fixture_sandbox: Path | None = None
    if spec.fixture_directory is not None:
        fixture_mount = spec.fixture_directory
        if runtime_name() == "native":
            # Native execution cannot enforce a read-only bind mount. Some tools write beside
            # their input, so give each probe a disposable copy instead of the source fixtures.
            fixture_sandbox = check_dir / ".fixture-sandbox"
            shutil.copytree(spec.fixture_directory, fixture_sandbox)
            fixture_mount = fixture_sandbox
        mounts.append((fixture_mount, "/fixtures", "ro"))
    command = container_command(
        [
            "pixi",
            "run",
            "--frozen",
            "--manifest-path",
            "/workspace/pixi.toml",
            "--",
            *spec.command,
        ],
        mounts=tuple(mounts),
        environment=spec.environment_variables,
        workdir="/work",
        interactive=spec.stdin_fixture is not None,
        name=container_name,
    )
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    notes: str | None = None
    observed: dict[str, Any] = {}
    before = {
        path.relative_to(check_dir).as_posix() for path in check_dir.rglob("*") if path.is_file()
    }
    try:
        completed = _run(
            command,
            timeout=spec.timeout_seconds,
            stdin_bytes=spec.stdin_fixture.read_bytes() if spec.stdin_fixture else None,
        )
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        stdout = completed.stdout.decode(errors="replace")
        stderr = completed.stderr.decode(errors="replace")
        combined = (stdout + "\n" + stderr).lower()
        crash_detected = any(marker in combined for marker in CRASH_PATTERNS)
        diagnostic_class = _diagnostic_class(stderr, crash_detected)
        created = sorted(
            path.relative_to(check_dir).as_posix()
            for path in check_dir.rglob("*")
            if path.is_file()
            and path.relative_to(check_dir).as_posix() not in before
            and path.name not in {"stdout.txt", "stderr.txt", "metadata.json", "result.json"}
        )
        observed = {
            "exit_code": completed.returncode,
            "timed_out": False,
            "crash_detected": crash_detected,
            "diagnostic_class": diagnostic_class,
            "stdout_bytes": len(completed.stdout),
            "stderr_bytes": len(completed.stderr),
            "created_files": created,
            "stdin_bytes": spec.stdin_fixture.stat().st_size if spec.stdin_fixture else 0,
        }
        if completed.returncode == 125:
            status = Status.ERROR
            notes = "Container runtime could not start or supervise the probe."
        elif _executable_launch_failed(completed.returncode, stderr):
            status = Status.ERROR
            observed["audit_error"] = "ExecutableLaunchFailure"
            notes = "The installed executable could not be launched in the audited environment."
        elif spec.error_contract:
            allowed_success = spec.allow_successful_empty_input and completed.returncode == 0
            exit_coherent = completed.returncode != 0 or allowed_success
            diagnostic_ok = allowed_success or (
                diagnostic_class == "SPECIFIC"
                if spec.diagnostic_expectation == "specific"
                else diagnostic_class in {"SPECIFIC", "GENERIC"}
            )
            status = (
                Status.PASS
                if exit_coherent and diagnostic_ok and not crash_detected and not created
                else Status.FAIL
            )
        else:
            status = (
                Status.PASS
                if completed.returncode in spec.allowed_exit_codes and not crash_detected
                else Status.FAIL
            )
        lowered = (stdout + "\n" + stderr).lower()
        if spec.required_all_text:
            matched = all(token.lower() in lowered for token in spec.required_all_text)
            observed["required_all_text_present"] = matched
            if status is Status.PASS and not matched:
                status = Status.FAIL
        if spec.required_any_text:
            matched = any(token.lower() in lowered for token in spec.required_any_text)
            observed["required_any_text_present"] = matched
            if status is Status.PASS and not matched:
                status = Status.FAIL
        if spec.expected_version is not None:
            matched = spec.expected_version.lower() in lowered
            observed["audited_version_present"] = matched
            if status is Status.PASS and not matched:
                status = Status.FAIL
        if spec.require_stdout_nonempty:
            stdout_nonempty = bool(stdout.strip())
            observed["stdout_nonempty"] = stdout_nonempty
            if status is Status.PASS and not stdout_nonempty:
                status = Status.FAIL
        if spec.stdout_parser is not None:
            stdout_valid, stdout_records, stdout_error = _inspect_output(
                stdout_path,
                spec.stdout_parser,
                allow_empty=spec.stdout_record_count == 0,
            )
            observed["stdout_parser"] = spec.stdout_parser
            observed["stdout_structurally_valid"] = stdout_valid
            observed["stdout_record_count"] = stdout_records
            observed["stdout_parser_error"] = stdout_error
            if status is Status.PASS and (
                not stdout_valid
                or (
                    spec.stdout_record_count is not None
                    and stdout_records != spec.stdout_record_count
                )
            ):
                status = Status.FAIL
        output_observations: list[dict[str, Any]] = []
        for expected in spec.expected_outputs:
            path = check_dir / expected.path
            exists = path.is_file()
            nonempty = exists and path.stat().st_size > 0
            structurally_valid, record_count, parser_error = (
                _inspect_output(
                    path,
                    expected.parser,
                    allow_empty=expected.record_count == 0,
                )
                if exists
                else (False, None, "missing")
            )
            output_observations.append(
                {
                    "path": expected.path,
                    "exists": exists,
                    "nonempty": nonempty,
                    "parser": expected.parser,
                    "structurally_valid": structurally_valid,
                    "record_count": record_count,
                    "parser_error": parser_error,
                }
            )
            if status is Status.PASS and (
                not exists
                or (expected.nonempty and not nonempty)
                or not structurally_valid
                or (expected.record_count is not None and record_count != expected.record_count)
            ):
                status = Status.FAIL
        if output_observations:
            observed["outputs"] = output_observations
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_bytes(exc.stdout or b"")
        stderr_path.write_bytes(exc.stderr or b"")
        cleanup_timed_out_container(container_name)
        observed = {"exit_code": None, "timed_out": True}
        status = Status.UNTESTABLE
        notes = "Probe exceeded the declared resource budget."
    except (OSError, ValueError) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        observed = {"exit_code": None, "audit_error": type(exc).__name__}
        notes = "Audit machinery could not start or supervise the probe."
    if fixture_sandbox is not None:
        shutil.rmtree(fixture_sandbox, ignore_errors=True)
    duration = time.monotonic() - clock
    metadata = {
        "schema_version": 2,
        "command": spec.command,
        "container_command": command,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "duration_seconds": duration,
        "environment_id": spec.environment.environment_id,
        "network_during_probe": False,
        "limits": {"cpus": 2, "memory_gib": 8, "pids": 256},
        "manifest_sha256": spec.manifest_sha256,
        "installation": spec.environment.package_record,
        **audit_code_identity(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    result = CheckResult(
        run_id=run_id,
        project_id=spec.project_id,
        snapshot_date=spec.snapshot_date,
        snapshot_commit=spec.snapshot_commit,
        executable_id=spec.executable_id,
        installation_id=spec.environment.installation_id,
        check_id=spec.check_id,
        probe_id=spec.probe_id,
        domain=spec.domain,
        status=status,
        expected={
            "timeout_seconds": spec.timeout_seconds,
            "allowed_exit_codes": list(spec.allowed_exit_codes),
            "diagnostic_expectation": spec.diagnostic_expectation,
            "network": "none",
        },
        observed=observed,
        tool=ToolIdentity(name="seebot-pixi-runner", version=__version__),
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


def cleanup_environment(environment: PixiEnvironment) -> int:
    """Remove only the per-project environment; retain the owned shared package cache."""
    size = sum(path.stat().st_size for path in environment.root.rglob("*") if path.is_file())
    shutil.rmtree(environment.root)
    return size
