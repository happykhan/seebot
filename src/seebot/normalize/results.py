"""Normalize immutable per-check results into web and analysis tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from seebot.models import CheckResult

CORE_COLUMNS = [
    "run_id",
    "project_id",
    "repository_id",
    "snapshot_date",
    "snapshot_commit",
    "source_component_id",
    "executable_id",
    "installation_id",
    "check_id",
    "probe_id",
    "domain",
    "status",
    "result_kind",
    "applicability",
    "method",
    "started_at",
    "duration_seconds",
    "environment_id",
    "config_sha256",
    "notes",
]
NESTED_COLUMNS = ["expected", "observed", "tool", "command", "evidence"]


def _natural_key(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(row.get(column) or "")
        for column in (
            "run_id",
            "project_id",
            "snapshot_date",
            "source_component_id",
            "executable_id",
            "check_id",
            "probe_id",
        )
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], *, analysis_ready: bool) -> None:
    columns = CORE_COLUMNS + (NESTED_COLUMNS if analysis_ready else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            output = dict(row)
            if analysis_ready:
                for column in NESTED_COLUMNS:
                    output[column] = json.dumps(output.get(column), sort_keys=True)
            writer.writerow(output)


def normalize_run(evidence_root: Path, results_root: Path, run_id: str) -> tuple[Path, Path]:
    target = results_root / run_id
    indexed: dict[tuple[str, ...], dict[str, Any]] = {}
    run_root = evidence_root / run_id
    for path in sorted(run_root.rglob("result.json")):
        row = CheckResult.model_validate_json(path.read_text(encoding="utf-8")).model_dump(
            mode="json"
        )
        # Evidence is rooted at <run>/<project>/....  Ignore archived or otherwise
        # misplaced result trees so a preserved stale contract cannot re-enter a
        # normalized run merely because it is stored beneath the run directory.
        relative = path.relative_to(run_root)
        if not relative.parts or relative.parts[0] != row["project_id"]:
            continue
        indexed[_natural_key(row)] = row
    if not indexed:
        raise ValueError(f"No completed check results found for run {run_id}")
    rows = [indexed[key] for key in sorted(indexed)]
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "checks.json"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    csv_path = target / "checks.csv"
    _write_csv(csv_path, rows, analysis_ready=False)
    return json_path, csv_path


def rebuild_global_results(results_root: Path) -> tuple[Path, Path]:
    """Build a deterministic fact table from immutable normalized runs.

    The natural key is (run_id, project_id, check_id). Conflicting duplicate
    keys are rejected instead of silently selecting one observation.
    """
    indexed: dict[tuple[str, ...], dict[str, Any]] = {}
    for path in sorted(results_root.glob("*/checks.json")):
        if path.parent.name == "global":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a result list in {path}")
        for row in payload:
            row = CheckResult.model_validate(row).model_dump(mode="json")
            key = _natural_key(row)
            previous = indexed.get(key)
            if previous is not None and previous != row:
                raise ValueError(f"Conflicting global result key {key} in {path}")
            indexed[key] = row
    if not indexed:
        raise ValueError(f"No normalized runs found under {results_root}")

    rows = [indexed[key] for key in sorted(indexed)]
    target = results_root / "global"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "check-results.json"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    csv_path = target / "check-results.csv"
    _write_csv(csv_path, rows, analysis_ready=True)
    return json_path, csv_path


def merge_normalized_batches(
    batch_paths: list[Path], results_root: Path, run_id: str
) -> tuple[Path, Path]:
    """Overlay complete project batches in order, with the newest batch winning."""
    projects: dict[str, list[dict[str, Any]]] = {}
    for path in batch_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a result list in {path}")
        current: dict[str, dict[tuple[str, ...], dict[str, Any]]] = {}
        for value in payload:
            row = CheckResult.model_validate(value).model_dump(mode="json")
            if row["run_id"] != run_id:
                raise ValueError(f"Expected run_id {run_id!r} in {path}, found {row['run_id']!r}")
            project_id = str(row["project_id"])
            indexed = current.setdefault(project_id, {})
            key = _natural_key(row)
            previous = indexed.get(key)
            if previous is not None and previous != row:
                raise ValueError(f"Conflicting batch result key {key} in {path}")
            indexed[key] = row
        for project_id, indexed in current.items():
            projects[project_id] = [indexed[key] for key in sorted(indexed)]
    if not projects:
        raise ValueError("No normalized batch results were provided")
    rows = sorted(
        (row for project_rows in projects.values() for row in project_rows), key=_natural_key
    )
    target = results_root / run_id
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "checks.json"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    csv_path = target / "checks.csv"
    _write_csv(csv_path, rows, analysis_ready=False)
    return json_path, csv_path
