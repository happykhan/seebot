"""Export normalized results for the Seebot web application."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seebot.analyzers.repository import repository_facts


def enrich_repository_rows(rows: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    """Derive newer repository facts from retained GitHub tree snapshots.

    Older pilot result rows remain immutable. The web view can nevertheless expose
    newly defined file-presence signals because the complete pinned tree response
    was retained as evidence.
    """
    for row in rows:
        if row.get("check_id") != "REPO-PRACTICES-001" or row.get("status") != "PASS":
            continue
        if "test_file_count" in row.get("observed", {}):
            continue
        evidence_path = root / row["evidence"]["stdout"]
        candidates = (
            [evidence_path]
            if evidence_path.exists()
            else sorted(
                (root / "evidence").glob(f"*/{row['package_id']}/REPO-PRACTICES-001/stdout.json")
            )
        )
        if not candidates:
            continue
        payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
        paths = [item["path"] for item in payload.get("tree", []) if item.get("type") == "blob"]
        identity = {
            key: row["observed"].get(key)
            for key in ("repository_url", "observed_commit", "tree_truncated")
        }
        row["observed"] = repository_facts(paths) | identity
    return rows
