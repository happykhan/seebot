"""Normalize immutable per-check results into web and analysis tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

CORE_COLUMNS = [
    "run_id",
    "package_id",
    "check_id",
    "domain",
    "status",
    "applicability",
    "method",
    "started_at",
    "duration_seconds",
    "environment_id",
    "config_sha256",
    "notes",
]
NESTED_COLUMNS = ["expected", "observed", "tool", "command", "evidence"]


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
    rows: list[dict[str, Any]] = []
    for path in sorted((evidence_root / run_id).rglob("result.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        raise ValueError(f"No completed check results found for run {run_id}")
    target = results_root / run_id
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "checks.json"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    csv_path = target / "checks.csv"
    _write_csv(csv_path, rows, analysis_ready=False)
    return json_path, csv_path


def rebuild_global_results(results_root: Path) -> tuple[Path, Path]:
    """Build a deterministic fact table from immutable normalized runs.

    The natural key is (run_id, package_id, check_id). Conflicting duplicate
    keys are rejected instead of silently selecting one observation.
    """
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in sorted(results_root.glob("*/checks.json")):
        if path.parent.name == "global":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a result list in {path}")
        for row in payload:
            key = (row["run_id"], row["package_id"], row["check_id"])
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
