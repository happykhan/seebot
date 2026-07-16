"""Manifest-driven planning and execution of installed-interface observations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from seebot.analyzers.dependencies import run_installed_dependency_advisories
from seebot.evidence import sha256_file
from seebot.fixtures import fixture_index
from seebot.models import Applicability, CheckResult, ResultKind, Status, ToolIdentity
from seebot.observations import write_measurement
from seebot.runtime.analyzers import AnalyzerEnvironment
from seebot.runtime.pixi import (
    ExpectedOutput,
    PixiEnvironment,
    PixiProbeSpec,
    cleanup_environment,
    command_is_installed,
    package_executables,
    prepare_environment,
    run_pixi_probe,
)

ROBUSTNESS_CHECKS = {
    "missing_input": "CLI-MISSING-INPUT-001",
    "empty_input": "CLI-EMPTY-INPUT-001",
    "semantically_empty_input": "CLI-SEMANTICALLY-EMPTY-INPUT-001",
    "malformed_input": "CLI-MALFORMED-INPUT-001",
    "wrong_format": "CLI-WRONG-FORMAT-001",
    "invalid_option": "CLI-INVALID-OPTION-001",
    "invalid_value": "CLI-INVALID-VALUE-001",
    "unwritable_output": "CLI-UNWRITABLE-OUTPUT-001",
}


def declared_command_names(manifest: dict[str, Any]) -> tuple[str, ...]:
    """Collect executable tokens from every reviewed argument-array command."""
    interface = manifest["interfaces"]
    commands = [*interface["help_commands"], *interface["version_commands"]]
    commands.extend(
        row["command"] for row in (manifest["valid_run"], manifest["streams"]) if row.get("command")
    )
    commands.extend(row["command"] for row in manifest["robustness"].values() if row.get("command"))
    names = {str(command[0]) for command in commands if command}
    if interface.get("primary"):
        names.add(str(interface["primary"]))
    return tuple(sorted(names, key=str.casefold))


def verify_installed_interface(
    manifest: dict[str, Any], environment: PixiEnvironment
) -> tuple[str, ...]:
    """Reject a curated interface that does not match the installed package payload."""
    project_id = str(manifest["project"]["id"])
    primary = str(manifest["interfaces"]["primary"])
    owned = package_executables(environment)
    missing = tuple(
        name
        for name in declared_command_names(manifest)
        if not command_is_installed(environment, name)
    )
    problems: list[str] = []
    if primary not in owned:
        problems.append(f"primary command {primary!r} is not owned by the requested package")
    if missing:
        problems.append("command(s) absent from the installed environment: " + ", ".join(missing))
    if problems:
        ordered = sorted(
            owned,
            key=lambda name: (
                name.casefold() != primary.casefold(),
                primary.casefold() not in name.casefold(),
                name.casefold(),
            ),
        )
        shown = ordered[:12]
        candidates = ", ".join(shown) if shown else "none recorded"
        if len(ordered) > len(shown):
            candidates += f" (+{len(ordered) - len(shown)} more)"
        raise ValueError(
            f"Installed interface preflight failed for {project_id}: {'; '.join(problems)}. "
            f"Package-owned executable candidates: {candidates}."
        )
    return owned


def _probe_id(check_id: str, command: list[str]) -> str:
    variant = "-".join(part.lstrip("-").replace("/", "_") for part in command[:3])
    return f"{check_id.lower()}:{variant or 'default'}"


def plan_usage_probes(
    manifest: dict[str, Any],
    environment: PixiEnvironment,
    *,
    fixture_directory: Path,
    manifest_sha256: str,
) -> list[PixiProbeSpec]:
    """Convert one reviewed project manifest into generic probe specifications."""
    project_id = str(manifest["project"]["id"])
    snapshot_date = str(manifest["repository"]["snapshot_date"])
    snapshot_commit = manifest["repository"]["snapshot_commit"]
    interface = manifest["interfaces"]
    version = manifest["installation"]["version"]
    specs: list[PixiProbeSpec] = []
    for command in interface["help_commands"]:
        specs.append(
            PixiProbeSpec(
                project_id=project_id,
                check_id="CLI-HELP-001",
                probe_id=_probe_id("CLI-HELP-001", command),
                domain="usage",
                command=command,
                # Cold imports for larger Python CLIs can exceed 30 seconds even though the
                # command then returns useful help normally (for example RGI and scanpy-cli).
                timeout_seconds=60,
                environment=environment,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                executable_id=command[0],
                fixture_directory=fixture_directory,
                required_any_text=("usage", "options", "commands", "arguments"),
                manifest_sha256=manifest_sha256,
            )
        )
    for command in interface["version_commands"]:
        specs.append(
            PixiProbeSpec(
                project_id=project_id,
                check_id="CLI-VERSION-001",
                probe_id=_probe_id("CLI-VERSION-001", command),
                domain="usage",
                command=command,
                timeout_seconds=15,
                environment=environment,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                executable_id=command[0],
                fixture_directory=fixture_directory,
                expected_version=str(version) if version else None,
                manifest_sha256=manifest_sha256,
            )
        )
    primary = interface["primary"]
    noargs_policy = interface["no_argument_policy"]
    if primary and noargs_policy not in {"stdin_filter", "unknown"}:
        allowed = (0,) if noargs_policy == "successful_noop" else (0, 1, 2, 64)
        specs.append(
            PixiProbeSpec(
                project_id=project_id,
                check_id="CLI-NOARGS-001",
                probe_id=f"cli-noargs-001:{primary}",
                domain="usage",
                command=[primary],
                timeout_seconds=15,
                environment=environment,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                executable_id=primary,
                allowed_exit_codes=allowed,
                fixture_directory=fixture_directory,
                manifest_sha256=manifest_sha256,
                required_any_text=("usage", "options", "input", "argument")
                if noargs_policy in {"help_or_usage_error", "requires_input"}
                else (),
            )
        )
    valid = manifest["valid_run"]
    if valid["status"] == "reviewed" and valid["command"]:
        specs.append(
            PixiProbeSpec(
                project_id=project_id,
                check_id="CLI-VALID-RUN-001",
                probe_id=f"cli-valid-run-001:{primary or valid['command'][0]}",
                domain="usage",
                command=valid["command"],
                timeout_seconds=int(valid["timeout_seconds"]),
                environment=environment,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                executable_id=primary or valid["command"][0],
                fixture_directory=fixture_directory,
                expected_outputs=tuple(ExpectedOutput(**row) for row in valid["expected_outputs"]),
                require_stdout_nonempty=bool(valid["expect_stdout"]),
                stdout_parser=valid["stdout_parser"],
                manifest_sha256=manifest_sha256,
            )
        )
    streams = manifest["streams"]
    if streams["applicability"] == "applicable" and streams["command"]:
        stdin_fixture = None
        if streams["stdin_fixture_id"]:
            stdin_fixture = fixture_directory / fixture_index()[streams["stdin_fixture_id"]]["path"]
        specs.append(
            PixiProbeSpec(
                project_id=project_id,
                check_id="CLI-STREAMS-001",
                probe_id=f"cli-streams-001:{primary or streams['command'][0]}",
                domain="usage",
                command=streams["command"],
                timeout_seconds=int(streams["timeout_seconds"]),
                environment=environment,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                executable_id=primary or streams["command"][0],
                fixture_directory=fixture_directory,
                require_stdout_nonempty=bool(streams["expect_stdout"]),
                stdout_parser=streams["stdout_parser"],
                stdin_fixture=stdin_fixture,
                manifest_sha256=manifest_sha256,
            )
        )
    for scenario, check_id in ROBUSTNESS_CHECKS.items():
        probe = manifest["robustness"][scenario]
        if probe["applicability"] != "applicable" or not probe["command"]:
            continue
        semantic_empty = scenario == "semantically_empty_input"
        specs.append(
            PixiProbeSpec(
                project_id=project_id,
                check_id=check_id,
                probe_id=f"{check_id.lower()}:{primary or probe['command'][0]}",
                domain="robustness",
                command=probe["command"],
                timeout_seconds=30,
                environment=environment,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                executable_id=primary or probe["command"][0],
                fixture_directory=fixture_directory,
                expected_outputs=tuple(
                    ExpectedOutput(**row) for row in probe.get("expected_outputs", [])
                ),
                require_stdout_nonempty=bool(probe.get("expect_stdout", False)),
                stdout_parser=probe.get("stdout_parser"),
                stdout_record_count=probe.get("stdout_record_count"),
                diagnostic_expectation=probe.get("diagnostic_expectation", "not_applicable"),
                error_contract=not semantic_empty,
                allow_successful_empty_input=scenario == "empty_input",
                manifest_sha256=manifest_sha256,
            )
        )
    return specs


def run_project_usage(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    run_id: str,
    output_root: Path,
    fixture_directory: Path,
    config_path: Path,
    analyzer_environment: AnalyzerEnvironment | None = None,
    checks: set[str] | None = None,
    force: bool = False,
    cleanup: bool = True,
) -> list[CheckResult]:
    """Install and run selectable Seebot probes for one project."""
    if manifest["installation"]["adapter"] != "pixi":
        raise NotImplementedError("Only the generic Pixi installation adapter is enabled")
    if manifest["curation"]["status"] != "reviewed":
        raise ValueError(f"{manifest['project']['id']} is not fully reviewed")
    fixture_ids = set(manifest["valid_run"]["fixture_ids"])
    fixture_ids.update(manifest["streams"]["fixture_ids"])
    fixture_ids.update(
        probe["fixture_id"]
        for probe in manifest["robustness"].values()
        if probe["fixture_id"] is not None
    )
    unknown = fixture_ids - set(fixture_index())
    if unknown:
        raise ValueError("Unknown fixture id(s): " + ", ".join(sorted(unknown)))
    project_id = manifest["project"]["id"]
    installation = manifest["installation"]
    interface = manifest["interfaces"]
    environment = prepare_environment(
        output_root / "work" / "environments" / project_id,
        cache_root=output_root / ".seebot-cache" / "pixi",
        project_id=project_id,
        package_name=installation["artifact"],
        version=str(installation["version"]),
        build=installation["build"],
        channels=installation["channels"],
    )
    try:
        verify_installed_interface(manifest, environment)
        specs = plan_usage_probes(
            manifest,
            environment,
            fixture_directory=fixture_directory,
            manifest_sha256=sha256_file(manifest_path),
        )
        if checks:
            specs = [spec for spec in specs if spec.check_id in checks or spec.domain in checks]
        results = [
            run_pixi_probe(
                spec,
                run_id=run_id,
                evidence_root=output_root / "evidence",
                config_path=config_path,
                force=force,
            )
            for spec in specs
        ]
        requested = checks or {"usage", "robustness"}
        if "dependencies" in requested or "DEP-ADVISORY-001" in requested:
            if analyzer_environment is None:
                raise ValueError("Installed dependency checks require an analyzer environment")
            results.append(
                run_installed_dependency_advisories(
                    analyzer_environment=analyzer_environment,
                    environment=environment,
                    project_id=project_id,
                    run_id=run_id,
                    evidence_root=output_root / "evidence",
                    config_path=config_path,
                    snapshot_date=manifest["repository"]["snapshot_date"],
                    snapshot_commit=manifest["repository"]["snapshot_commit"],
                    force=force,
                )
            )
        status_rows: list[tuple[str, str, Status, str, Applicability]] = []
        valid = manifest["valid_run"]
        if ("usage" in requested or "CLI-VALID-RUN-001" in requested) and valid[
            "status"
        ] == "untestable":
            status_rows.append(
                (
                    "CLI-VALID-RUN-001",
                    "valid-run:untestable",
                    Status.UNTESTABLE,
                    valid["untestable_reason"] or "No meaningful bounded miniature run.",
                    Applicability.APPLICABLE,
                )
            )
        stream = manifest["streams"]
        if ("usage" in requested or "CLI-STREAMS-001" in requested) and stream[
            "applicability"
        ] == "not_applicable":
            status_rows.append(
                (
                    "CLI-STREAMS-001",
                    "streams:not-applicable",
                    Status.NOT_APPLICABLE,
                    stream["reason"] or "The documented interface has no stream mode.",
                    Applicability.NOT_APPLICABLE,
                )
            )
        if ("usage" in requested or "CLI-NOARGS-001" in requested) and interface[
            "no_argument_policy"
        ] == "stdin_filter":
            status_rows.append(
                (
                    "CLI-NOARGS-001",
                    "noargs:not-applicable",
                    Status.NOT_APPLICABLE,
                    "No-argument invocation is the documented standard-input mode.",
                    Applicability.NOT_APPLICABLE,
                )
            )
        for scenario, check_id in ROBUSTNESS_CHECKS.items():
            probe = manifest["robustness"][scenario]
            if not ("robustness" in requested or check_id in requested):
                continue
            if probe["applicability"] == "not_applicable":
                status_rows.append(
                    (
                        check_id,
                        f"{scenario}:not-applicable",
                        Status.NOT_APPLICABLE,
                        probe["reason"] or "Scenario does not apply to this interface.",
                        Applicability.NOT_APPLICABLE,
                    )
                )
            elif probe["applicability"] == "unknown":
                status_rows.append(
                    (
                        check_id,
                        f"{scenario}:not-run",
                        Status.NOT_RUN,
                        probe["reason"] or "The scenario has not yet been curated.",
                        Applicability.UNKNOWN,
                    )
                )
        for check_id, probe_id, status, reason, applicability in status_rows:
            results.append(
                write_measurement(
                    project_id=project_id,
                    run_id=run_id,
                    check_id=check_id,
                    probe_id=probe_id,
                    domain=(
                        "robustness" if check_id in set(ROBUSTNESS_CHECKS.values()) else "usage"
                    ),
                    status=status,
                    observed={"reason": reason},
                    evidence_root=output_root / "evidence",
                    config_path=config_path,
                    snapshot_date=manifest["repository"]["snapshot_date"],
                    snapshot_commit=manifest["repository"]["snapshot_commit"],
                    executable_id=manifest["interfaces"]["primary"],
                    installation_id=environment.installation_id,
                    result_kind=ResultKind.CONTRACT,
                    applicability=applicability,
                    tool=ToolIdentity(name="Seebot manifest dispatcher", version="2"),
                    expected={"applicability": applicability.value},
                    notes=reason,
                    force=force,
                )
            )
        return results
    finally:
        if cleanup and environment.root.exists() and os.environ.get("SEEBOT_OFFLINE") != "1":
            cleanup_environment(environment)
