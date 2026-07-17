"""Orchestration for source-derived measurements at one repository snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seebot.analyzers.native import run_non_python_native_analyzers
from seebot.analyzers.python import run_python_analyzers
from seebot.analyzers.structure import production_files, run_structural_observations
from seebot.models import CheckResult, Status, ToolIdentity
from seebot.observations import write_measurement
from seebot.runtime.analyzers import AnalyzerEnvironment


def run_source_observations(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    checkout: Path,
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    snapshot_date: str,
    snapshot_commit: str | None,
    analyzer_environment: AnalyzerEnvironment,
    include_native: bool = True,
    force: bool = False,
) -> list[CheckResult]:
    project_id = manifest["project"]["id"]
    results = run_structural_observations(
        manifest=manifest,
        checkout=checkout,
        run_id=run_id,
        evidence_root=evidence_root,
        config_path=config_root / "rubric.yaml",
        snapshot_date=snapshot_date,
        snapshot_commit=snapshot_commit,
        force=force,
    )
    if not include_native:
        return results
    languages = manifest["source"]["language_roots"]
    if "python" in languages:
        files, _ = production_files(checkout, manifest, "python")
        results.extend(
            run_python_analyzers(
                environment=analyzer_environment,
                checkout=checkout,
                files=files,
                project_id=project_id,
                run_id=run_id,
                evidence_root=evidence_root,
                config_root=config_root,
                force=force,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
            )
        )
    for language in sorted(set(languages) - {"python"}):
        files, _ = production_files(checkout, manifest, language)
        results.extend(
            run_non_python_native_analyzers(
                environment=analyzer_environment,
                manifest=manifest,
                checkout=checkout,
                language=language,
                files=files,
                run_id=run_id,
                evidence_root=evidence_root,
                config_root=config_root,
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                force=force,
            )
        )
        results.append(
            write_measurement(
                project_id=project_id,
                run_id=run_id,
                check_id="SRC-DEAD-CODE-001",
                probe_id=f"source:{language}:dead-code",
                domain="source",
                status=Status.NOT_APPLICABLE,
                observed={
                    "language": language,
                    "reason": "No frozen dead-code analyzer for this language profile.",
                },
                evidence_root=evidence_root,
                config_path=config_root / "rubric.yaml",
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                source_component_id=f"{language}:production",
                tool=ToolIdentity(name="Seebot analyzer dispatcher", version="2"),
                force=force,
            )
        )
    return results
