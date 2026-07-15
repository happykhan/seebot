"""End-to-end project assessment orchestration with disposable checkouts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from seebot.analyzers.repository import clone_snapshot, run_repository_observations
from seebot.analyzers.source import run_source_observations
from seebot.models import CheckResult, Status, ToolIdentity
from seebot.observations import write_measurement
from seebot.runtime.analyzers import AnalyzerEnvironment

SOURCE_CHECKS = (
    "SRC-INVENTORY-001",
    "SRC-FILE-LENGTH-001",
    "SRC-FUNCTION-STRUCTURE-001",
    "SRC-COMPLEXITY-001",
    "SRC-DUPLICATION-001",
    "SRC-DOCUMENTATION-001",
    "SRC-NATIVE-LINT-001",
    "SRC-NATIVE-SECURITY-001",
    "SRC-DEAD-CODE-001",
)


def _not_existing(
    *,
    manifest: dict[str, Any],
    snapshot_date: str,
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    force: bool,
) -> list[CheckResult]:
    rows: list[CheckResult] = []
    for language in sorted(manifest["source"]["language_roots"]):
        for check_id in SOURCE_CHECKS:
            rows.append(
                write_measurement(
                    project_id=manifest["project"]["id"],
                    run_id=run_id,
                    check_id=check_id,
                    probe_id=f"source:{language}:not-existing",
                    domain="source",
                    status=Status.NOT_EXISTING,
                    observed={
                        "language": language,
                        "reason": "Repository had no commit at or before this snapshot date.",
                    },
                    evidence_root=evidence_root,
                    config_path=config_root / "rubric.yaml",
                    snapshot_date=snapshot_date,
                    snapshot_commit=None,
                    source_component_id=f"{language}:production",
                    tool=ToolIdentity(name="Seebot snapshot resolver", version="2"),
                    force=force,
                )
            )
    return rows


def run_repository_and_source(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    analyzer_environment: AnalyzerEnvironment,
    run_id: str,
    output_root: Path,
    config_root: Path,
    include_history: bool = True,
    include_repository: bool = True,
    include_source: bool = True,
    force: bool = False,
    cleanup: bool = True,
) -> list[CheckResult]:
    """Collect current repository facts and current/historical source observations."""
    repository = manifest["repository"]
    repository_url = repository["url"]
    current_commit = repository["snapshot_commit"]
    if not repository_url or not current_commit:
        raise ValueError(f"{manifest['project']['id']} has no resolved current snapshot")
    snapshots: list[tuple[str, str | None]] = [(repository["snapshot_date"], current_commit)]
    if include_history and include_source:
        snapshots = [
            *sorted((repository.get("historical_commits") or {}).items()),
            *snapshots,
        ]
    results: list[CheckResult] = []
    for snapshot_date, commit in snapshots:
        if commit is None and include_source:
            results.extend(
                _not_existing(
                    manifest=manifest,
                    snapshot_date=snapshot_date,
                    run_id=run_id,
                    evidence_root=output_root / "evidence",
                    config_root=config_root,
                    force=force,
                )
            )
            continue
        if commit is None:
            continue
        checkout = output_root / "work" / "checkouts" / manifest["project"]["id"] / snapshot_date
        clone_snapshot(repository_url, commit, checkout)
        try:
            if include_repository and snapshot_date == repository["snapshot_date"]:
                results.extend(
                    run_repository_observations(
                        manifest=manifest,
                        checkout=checkout,
                        run_id=run_id,
                        evidence_root=output_root / "evidence",
                        config_path=config_root / "rubric.yaml",
                        force=force,
                    )
                )
            if include_source:
                results.extend(
                    run_source_observations(
                        manifest_path=manifest_path,
                        manifest=manifest,
                        checkout=checkout,
                        run_id=run_id,
                        evidence_root=output_root / "evidence",
                        config_root=config_root,
                        snapshot_date=snapshot_date,
                        snapshot_commit=commit,
                        analyzer_environment=analyzer_environment,
                        force=force,
                    )
                )
        finally:
            if cleanup:
                shutil.rmtree(checkout, ignore_errors=True)
    return results
