"""Current-snapshot dependency advisory observations using OSV-Scanner."""

from __future__ import annotations

import json
import re
import subprocess
import time
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from seebot.evidence import audit_code_identity, evidence_path, sha256_file
from seebot.models import (
    Applicability,
    CheckResult,
    EvidencePaths,
    ResultKind,
    Status,
    ToolIdentity,
)
from seebot.runtime.analyzers import AnalyzerEnvironment, analyzer_command
from seebot.runtime.pixi import PixiEnvironment


def _fixed_versions(vulnerability: dict[str, Any]) -> list[str]:
    versions: set[str] = set()
    for affected in vulnerability.get("affected", []):
        for value_range in affected.get("ranges", []):
            for event in value_range.get("events", []):
                fixed = event.get("fixed")
                if fixed:
                    versions.add(str(fixed))
    return sorted(versions)


def _severity(vulnerability: dict[str, Any]) -> list[str]:
    values = vulnerability.get("severity") or []
    return sorted(
        {
            f"{row.get('type', 'UNKNOWN')}:{row.get('score', 'UNKNOWN')}"
            for row in values
            if isinstance(row, dict)
        }
    )


def _parse(payload: dict[str, Any]) -> tuple[dict[str, Any], Status, Applicability, str | None]:
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        reason = "OSV-Scanner detected no supported dependency manifest or lockfile."
        return (
            {
                "analyzer": "OSV-Scanner",
                "supported_sources": [],
                "advisory_count": 0,
                "advisories": [],
                "reason": reason,
            },
            Status.NOT_APPLICABLE,
            Applicability.NOT_APPLICABLE,
            reason,
        )
    sources: set[str] = set()
    advisories: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for result in results:
        source = result.get("source") if isinstance(result, dict) else None
        source_path = "UNKNOWN"
        if isinstance(source, dict) and source.get("path"):
            source_path = str(source["path"]).removeprefix("/source/")
            sources.add(source_path)
        for package_row in result.get("packages", []) if isinstance(result, dict) else []:
            package = package_row.get("package") or {}
            name = str(package.get("name") or "UNKNOWN")
            version = str(package.get("version") or package.get("commit") or "UNKNOWN")
            ecosystem = str(package.get("ecosystem") or "UNKNOWN")
            for vulnerability in package_row.get("vulnerabilities", []):
                advisory_id = str(vulnerability.get("id") or "UNKNOWN")
                advisories[(advisory_id, name, version, source_path)] = {
                    "advisory_id": advisory_id,
                    "aliases": sorted(map(str, vulnerability.get("aliases") or [])),
                    "ecosystem": ecosystem,
                    "dependency": name,
                    "resolved_version": version,
                    "source": source_path,
                    "native_severity": _severity(vulnerability),
                    "fixed_versions": _fixed_versions(vulnerability),
                }
    ordered = [advisories[key] for key in sorted(advisories)]
    return (
        {
            "analyzer": "OSV-Scanner",
            "supported_sources": sorted(sources),
            "advisory_count": len(ordered),
            "advisories": ordered,
        },
        Status.OBSERVED,
        Applicability.APPLICABLE,
        None,
    )


def _parse_cpan_audit(payload: dict[str, Any], source: str) -> list[dict[str, Any]]:
    advisories: list[dict[str, Any]] = []
    distributions = payload.get("dists")
    if not isinstance(distributions, dict):
        return advisories
    for distribution, details in distributions.items():
        if not isinstance(details, dict):
            continue
        version = str(details.get("version") or "UNKNOWN")
        for advisory in details.get("advisories", []):
            if not isinstance(advisory, dict):
                continue
            advisory_id = str(
                advisory.get("id") or advisory.get("cpansa_id") or advisory.get("cve") or "UNKNOWN"
            )
            aliases = advisory.get("cves") or advisory.get("aliases") or []
            advisories.append(
                {
                    "advisory_id": advisory_id,
                    "aliases": sorted(
                        map(str, aliases if isinstance(aliases, list) else [aliases])
                    ),
                    "ecosystem": "CPAN",
                    "dependency": str(distribution),
                    "resolved_version": version,
                    "source": source,
                    "native_severity": [],
                    "fixed_versions": [],
                }
            )
    return sorted(advisories, key=lambda row: (row["advisory_id"], row["dependency"]))


def _requirement_record(
    value: str, *, role: str, source: str, group: str | None = None
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ecosystem": "PyPI",
        "role": role,
        "source": source,
        "raw": value,
    }
    if group is not None:
        record["group"] = group
    try:
        requirement = Requirement(value)
    except InvalidRequirement:
        record.update({"name": "UNKNOWN", "parse_status": "ERROR"})
        return record
    record.update(
        {
            "name": requirement.name,
            "specifier": str(requirement.specifier) or None,
            "marker": str(requirement.marker) if requirement.marker else None,
            "extras": sorted(requirement.extras),
            "parse_status": "OBSERVED",
        }
    )
    return record


def parse_python_dependency_declarations(checkout: Path) -> list[dict[str, Any]]:
    """Read standard Python dependency declarations without resolving or executing them."""
    path = checkout / "pyproject.toml"
    if not path.is_file():
        return []
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return [
            {
                "ecosystem": "PyPI",
                "role": "UNKNOWN",
                "source": "pyproject.toml",
                "name": "UNKNOWN",
                "parse_status": "ERROR",
            }
        ]
    records: list[dict[str, Any]] = []
    project = payload.get("project")
    if isinstance(project, dict):
        for value in project.get("dependencies", []):
            if isinstance(value, str):
                records.append(_requirement_record(value, role="runtime", source="pyproject.toml"))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group, values in optional.items():
                if not isinstance(values, list):
                    continue
                for value in values:
                    if isinstance(value, str):
                        records.append(
                            _requirement_record(
                                value,
                                role="optional",
                                source="pyproject.toml",
                                group=str(group),
                            )
                        )
    build_system = payload.get("build-system")
    if isinstance(build_system, dict):
        for value in build_system.get("requires", []):
            if isinstance(value, str):
                records.append(_requirement_record(value, role="build", source="pyproject.toml"))
    dependency_groups = payload.get("dependency-groups")
    if isinstance(dependency_groups, dict):
        for group, values in dependency_groups.items():
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str):
                    records.append(
                        _requirement_record(
                            value,
                            role="development",
                            source="pyproject.toml",
                            group=str(group),
                        )
                    )
    return sorted(
        records,
        key=lambda row: (
            str(row.get("role")),
            str(row.get("group", "")),
            str(row.get("name")),
            str(row.get("raw", "")),
        ),
    )


def _conda_dependency_name(value: str) -> str:
    return re.split(r"[ <>=!~]", value.strip(), maxsplit=1)[0]


def reachable_conda_packages(
    records: Sequence[dict[str, Any]], root_package: str
) -> list[dict[str, Any]]:
    """Return the exact Pixi/Conda dependency closure rooted at the audited package."""
    by_name = {
        canonicalize_name(str(record.get("name"))): record
        for record in records
        if record.get("name")
    }
    pending = [canonicalize_name(root_package)]
    visited: set[str] = set()
    output: list[dict[str, Any]] = []
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        record = by_name.get(name)
        if record is None:
            continue
        output.append(record)
        dependencies = record.get("depends")
        if isinstance(dependencies, list):
            pending.extend(
                canonicalize_name(_conda_dependency_name(str(value))) for value in dependencies
            )
    return sorted(output, key=lambda row: canonicalize_name(str(row.get("name", ""))))


def _properties(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")) or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _has_any_conda_package(records: Sequence[Mapping[str, Any]], names: set[str]) -> bool:
    return any(canonicalize_name(str(record.get("name", ""))) in names for record in records)


def discover_installed_ecosystem_packages(
    prefix: Path, *, include_maven: bool = True, include_npm: bool = True
) -> list[dict[str, str]]:
    """Inventory exact language packages present in a disposable Pixi prefix."""
    packages: dict[tuple[str, str, str], dict[str, str]] = {}
    for metadata in sorted(prefix.glob("lib/python*/site-packages/*.dist-info/METADATA")):
        try:
            message = Parser().parsestr(metadata.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        name = message.get("Name")
        version = message.get("Version")
        if name and version:
            key: tuple[str, str, str] = ("PyPI", str(canonicalize_name(name)), version)
            packages[key] = {
                "ecosystem": "PyPI",
                "name": name,
                "version": version,
                "source": metadata.relative_to(prefix).as_posix(),
            }
    if include_maven:
        for jar in sorted(prefix.rglob("*.jar")):
            try:
                with zipfile.ZipFile(jar) as archive:
                    property_names = sorted(
                        name
                        for name in archive.namelist()
                        if name.startswith("META-INF/maven/") and name.endswith("/pom.properties")
                    )
                    for property_name in property_names:
                        values = _properties(
                            archive.read(property_name).decode(encoding="utf-8", errors="replace")
                        )
                        group = values.get("groupId")
                        artifact = values.get("artifactId")
                        version = values.get("version")
                        if group and artifact and version:
                            name = f"{group}:{artifact}"
                            maven_key = ("Maven", name, version)
                            packages[maven_key] = {
                                "ecosystem": "Maven",
                                "name": name,
                                "version": version,
                                "source": jar.relative_to(prefix).as_posix(),
                            }
            except (OSError, ValueError, zipfile.BadZipFile):
                continue
    if include_npm:
        for package_json in sorted(prefix.rglob("package.json")):
            if "node_modules" not in package_json.parts:
                continue
            try:
                payload = json.loads(package_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            name = payload.get("name") if isinstance(payload, dict) else None
            version = payload.get("version") if isinstance(payload, dict) else None
            if isinstance(name, str) and isinstance(version, str):
                npm_key = ("npm", name, version)
                packages[npm_key] = {
                    "ecosystem": "npm",
                    "name": name,
                    "version": version,
                    "source": package_json.relative_to(prefix).as_posix(),
                }
    return [packages[key] for key in sorted(packages)]


def run_installed_dependency_advisories(
    *,
    analyzer_environment: AnalyzerEnvironment,
    environment: PixiEnvironment,
    project_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    snapshot_date: str,
    snapshot_commit: str,
    force: bool = False,
) -> CheckResult:
    """Scan exact language-package versions present in the audited Pixi prefix."""
    check_id = "DEP-ADVISORY-001"
    probe_id = "dependencies:installed-environment"
    safe_probe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", probe_id)
    target = evidence_root / run_id / project_id / snapshot_date / check_id / safe_probe
    result_path = target / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    target.mkdir(parents=True, exist_ok=True)
    stdout_path = target / "stdout.txt"
    stderr_path = target / "stderr.txt"
    metadata_path = target / "metadata.json"
    inventory_path = target / "inventory.json"
    prefix = environment.root / ".pixi" / "envs" / "default"
    conda_records = reachable_conda_packages(
        environment.package_records, str(environment.package_record.get("name", project_id))
    )
    conda_packages = [
        {
            key: record.get(key)
            for key in ("name", "version", "build", "channel", "subdir")
            if record.get(key) is not None
        }
        for record in conda_records
    ]
    include_maven = _has_any_conda_package(
        conda_records, {"java", "maven", "openjdk", "jdk", "jre"}
    )
    include_npm = _has_any_conda_package(conda_records, {"nodejs", "npm", "pnpm", "yarn"})
    ecosystem_packages = discover_installed_ecosystem_packages(
        prefix,
        include_maven=include_maven,
        include_npm=include_npm,
    )
    inventory = {
        "installation_id": environment.installation_id,
        "pixi_lock_sha256": sha256_file(environment.lock_path),
        "conda_packages": conda_packages,
        "ecosystem_packages": ecosystem_packages,
        "ecosystem_scan_policy": {
            "pypi": True,
            "maven": include_maven,
            "npm": include_npm,
        },
    }
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    command = [
        "osv-scanner",
        "scan",
        "source",
        "--format=json",
        "--verbosity=error",
        "--all-packages",
        "--lockfile",
        "osv-scanner:/source/osv-scanner.json",
    ]
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    applicability = Applicability.UNKNOWN
    observed: dict[str, Any] = {
        "scan_scope": "installed_environment",
        "installation_id": environment.installation_id,
        "conda_packages": conda_packages,
        "conda_package_count": len(conda_packages),
        "ecosystem_packages": ecosystem_packages,
        "ecosystem_package_count": len(ecosystem_packages),
    }
    notes: str | None = None
    exit_code: int | None = None
    try:
        if not ecosystem_packages:
            reason = (
                "The installed Pixi environment was inventoried, but it contained no exact "
                "PyPI, Maven, or npm package metadata that OSV-Scanner could match."
            )
            observed.update(
                {
                    "analyzer": "OSV-Scanner",
                    "supported_sources": [],
                    "advisory_count": None,
                    "advisories": [],
                    "reason": reason,
                }
            )
            status = Status.NOT_APPLICABLE
            applicability = Applicability.NOT_APPLICABLE
            notes = reason
            stdout_path.write_text('{"results": []}\n', encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
        else:
            input_root = target / "input"
            input_root.mkdir(exist_ok=True)
            scanner_input = input_root / "osv-scanner.json"
            scanner_input.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "packages": [
                                    {
                                        "package": {
                                            "name": package["name"],
                                            "version": package["version"],
                                            "ecosystem": package["ecosystem"],
                                        }
                                    }
                                    for package in ecosystem_packages
                                ]
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            completed = analyzer_command(
                analyzer_environment.root,
                command,
                source=input_root,
                work=target,
                network="bridge",
                timeout=300,
            )
            exit_code = completed.returncode
            stdout = completed.stdout.decode(errors="replace")
            stderr = completed.stderr.decode(errors="replace")
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            if completed.returncode not in {0, 1}:
                observed.update(
                    {"exit_code": completed.returncode, "audit_error": "scanner_failed"}
                )
                notes = "Dependency scanner machinery failed; no project judgement was inferred."
            else:
                parsed, status, applicability, notes = _parse(json.loads(stdout or "{}"))
                source_labels = sorted(
                    {
                        f"installed-environment:{package['ecosystem']}"
                        for package in ecosystem_packages
                    }
                )
                for advisory in parsed.get("advisories", []):
                    if isinstance(advisory, dict):
                        advisory["source"] = f"installed-environment:{advisory['ecosystem']}"
                parsed["supported_sources"] = source_labels
                parsed["exit_code"] = completed.returncode
                observed.update(parsed)
                status = Status.OBSERVED
                applicability = Applicability.APPLICABLE
                notes = None
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_bytes(exc.stdout or b"")
        stderr_path.write_bytes(exc.stderr or b"")
        observed["timed_out"] = True
        status = Status.UNTESTABLE
        applicability = Applicability.APPLICABLE
        notes = "Installed dependency advisory lookup exceeded its resource budget."
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        observed["audit_error"] = type(exc).__name__
        notes = "Dependency scanner machinery failed; no project judgement was inferred."
    duration = time.monotonic() - clock
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "command": command if ecosystem_packages else None,
                "exit_code": exit_code,
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "duration_seconds": duration,
                "environment_id": environment.environment_id,
                "network": "bridge for current OSV advisory lookup",
                "inventory": evidence_path(inventory_path, evidence_root),
                "inventory_sha256": sha256_file(inventory_path),
                **audit_code_identity(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = CheckResult(
        run_id=run_id,
        project_id=project_id,
        repository_id=None,
        snapshot_date=snapshot_date,
        snapshot_commit=snapshot_commit,
        source_component_id=None,
        executable_id=None,
        installation_id=environment.installation_id,
        check_id=check_id,
        probe_id=probe_id,
        domain="dependencies",
        status=status,
        result_kind=ResultKind.MEASUREMENT,
        applicability=applicability,
        method="automated_with_manifest",
        expected={
            "current_only": True,
            "basis": "exact packages installed in the audited Pixi environment",
            "network": "OSV advisory service",
        },
        observed=observed,
        tool=ToolIdentity(name="Pixi inventory with OSV-Scanner", version="0.72.2 / 2.4.0"),
        command=command if ecosystem_packages else None,
        started_at=started,
        duration_seconds=duration,
        environment_id=environment.environment_id,
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


def run_dependency_advisories(
    *,
    environment: AnalyzerEnvironment,
    checkout: Path,
    project_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    snapshot_date: str,
    snapshot_commit: str,
    force: bool = False,
) -> CheckResult:
    """Parse dependency files only; never invoke package managers or project code."""
    check_id = "DEP-ADVISORY-001"
    probe_id = "dependencies:osv-scanner"
    safe_probe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", probe_id)
    target = evidence_root / run_id / project_id / snapshot_date / check_id / safe_probe
    result_path = target / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    target.mkdir(parents=True, exist_ok=True)
    stdout_path = target / "stdout.txt"
    stderr_path = target / "stderr.txt"
    metadata_path = target / "metadata.json"
    command = [
        "osv-scanner",
        "scan",
        "source",
        "--format=json",
        "--verbosity=error",
        "--all-packages",
        "--recursive",
        "/source",
    ]
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    applicability = Applicability.UNKNOWN
    declared_dependencies = parse_python_dependency_declarations(checkout)
    observed: dict[str, Any] = {
        "scan_scope": "repository",
        "declared_dependencies": declared_dependencies,
    }
    notes: str | None = None
    exit_code: int | None = None
    try:
        completed = analyzer_command(
            environment.root,
            command,
            source=checkout,
            work=target,
            network="bridge",
            timeout=300,
        )
        exit_code = completed.returncode
        stdout = completed.stdout.decode(errors="replace")
        stderr = completed.stderr.decode(errors="replace")
        if completed.returncode == 128 and "no package sources found" in stderr.lower():
            parsed, status, applicability, notes = _parse({"results": []})
            observed.update(parsed)
            observed["exit_code"] = completed.returncode
        elif completed.returncode not in {0, 1}:
            observed.update({"exit_code": completed.returncode, "audit_error": "scanner_failed"})
            notes = "Dependency scanner machinery failed; no project judgement was inferred."
        else:
            parsed, status, applicability, notes = _parse(json.loads(stdout or "{}"))
            observed.update(parsed)
            observed["exit_code"] = completed.returncode
        cpan_sources = sorted(
            {
                path.parent.relative_to(checkout).as_posix() or "."
                for name in ("cpanfile", "cpanfile.snapshot")
                for path in checkout.rglob(name)
                if not any(part in {".git", "vendor", "third_party"} for part in path.parts)
            }
        )
        cpan_payloads: list[dict[str, Any]] = []
        cpan_stderr: list[str] = []
        for directory in cpan_sources:
            cpan_command = [
                "/workspace/perl5/bin/cpan-audit",
                "deps",
                f"/source/{directory}" if directory != "." else "/source",
                "--json",
                "--exit-zero",
            ]
            cpan_completed = analyzer_command(
                environment.root,
                cpan_command,
                source=checkout,
                work=target,
                network="none",
                timeout=300,
            )
            cpan_stderr.append(cpan_completed.stderr.decode(errors="replace"))
            if cpan_completed.returncode != 0:
                raise OSError(f"CPAN Audit failed with exit code {cpan_completed.returncode}")
            cpan_payload = json.loads(cpan_completed.stdout.decode(errors="replace") or "{}")
            cpan_payloads.append(cpan_payload)
            source_names = [
                f"{directory}/{name}" if directory != "." else name
                for name in ("cpanfile.snapshot", "cpanfile")
                if (checkout / directory / name).is_file()
            ]
            cpan_source = source_names[0]
            observed.setdefault("supported_sources", []).extend(source_names)
            observed.setdefault("advisories", []).extend(
                _parse_cpan_audit(cpan_payload, cpan_source)
            )
        if cpan_sources:
            observed["analyzer"] = "OSV-Scanner and CPAN Audit"
            observed["supported_sources"] = sorted(set(observed["supported_sources"]))
            observed["advisories"] = sorted(
                observed["advisories"],
                key=lambda row: (row["advisory_id"], row["dependency"], row.get("source", "")),
            )
            observed["advisory_count"] = len(observed["advisories"])
            status = Status.OBSERVED
            applicability = Applicability.APPLICABLE
            notes = None
        stdout_path.write_text(
            json.dumps(
                {"osv_scanner": json.loads(stdout or "{}"), "cpan_audit": cpan_payloads}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        stderr_path.write_text(stderr + "".join(cpan_stderr), encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_bytes(exc.stdout or b"")
        stderr_path.write_bytes(exc.stderr or b"")
        observed["timed_out"] = True
        status = Status.UNTESTABLE
        applicability = Applicability.APPLICABLE
        notes = "Dependency advisory lookup exceeded its resource budget."
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        observed["audit_error"] = type(exc).__name__
        notes = "Dependency scanner machinery failed; no project judgement was inferred."
    duration = time.monotonic() - clock
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "command": command,
                "exit_code": exit_code,
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "duration_seconds": duration,
                "environment_id": environment.environment_id,
                "network": "bridge for current OSV advisory lookup",
                **audit_code_identity(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = CheckResult(
        run_id=run_id,
        project_id=project_id,
        repository_id=None,
        snapshot_date=snapshot_date,
        snapshot_commit=snapshot_commit,
        source_component_id=None,
        check_id=check_id,
        probe_id=probe_id,
        domain="dependencies",
        status=status,
        result_kind=ResultKind.MEASUREMENT,
        applicability=applicability,
        method="automated_with_manifest",
        expected={"current_only": True, "network": "OSV advisory service"},
        observed=observed,
        tool=ToolIdentity(
            name="OSV-Scanner with CPAN Audit fallback", version="2.4.0 / 20260622.001"
        ),
        command=command,
        started_at=started,
        duration_seconds=duration,
        environment_id=environment.environment_id,
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
