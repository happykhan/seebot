"""Deterministic source tree inventory with curated path exclusions."""

from __future__ import annotations

import hashlib
from pathlib import Path


def inventory_tree(root: Path, excluded: list[Path] | None = None) -> list[dict[str, object]]:
    excluded_resolved = [(root / path).resolve() for path in (excluded or [])]
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if any(resolved == skip or resolved.is_relative_to(skip) for skip in excluded_resolved):
            continue
        content = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows
