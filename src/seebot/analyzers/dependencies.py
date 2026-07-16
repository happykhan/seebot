"""Current-snapshot dependency advisory observations using OSV-Scanner."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
        "--recursive",
        "/source",
    ]
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    applicability = Applicability.UNKNOWN
    observed: dict[str, Any] = {}
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
            observed, status, applicability, notes = _parse({"results": []})
            observed["exit_code"] = completed.returncode
        elif completed.returncode not in {0, 1}:
            observed = {"exit_code": completed.returncode, "audit_error": "scanner_failed"}
            notes = "Dependency scanner machinery failed; no project judgement was inferred."
        else:
            observed, status, applicability, notes = _parse(json.loads(stdout or "{}"))
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
        observed = {"timed_out": True}
        status = Status.UNTESTABLE
        applicability = Applicability.APPLICABLE
        notes = "Dependency advisory lookup exceeded its resource budget."
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        observed = {"audit_error": type(exc).__name__}
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
