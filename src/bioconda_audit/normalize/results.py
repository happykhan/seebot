"""Normalize immutable per-check results into web and analysis tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


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
    columns = [
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
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path
