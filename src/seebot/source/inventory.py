"""Deterministic source tree inventory with curated path exclusions."""

from __future__ import annotations

import hashlib
from pathlib import Path

from seebot.source.classify import classify_language, classify_role


def inventory_tree(
    root: Path,
    excluded: list[Path] | None = None,
    *,
    test_paths: list[Path] | None = None,
    documentation_paths: list[Path] | None = None,
    generated_paths: list[Path] | None = None,
    vendored_paths: list[Path] | None = None,
) -> list[dict[str, object]]:
    excluded_resolved = [(root / path).resolve() for path in (excluded or [])]
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if any(resolved == skip or resolved.is_relative_to(skip) for skip in excluded_resolved):
            continue
        content = path.read_bytes()
        relative = path.relative_to(root)
        rows.append(
            {
                "path": relative.as_posix(),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "language": classify_language(relative),
                "source_role": classify_role(
                    relative,
                    test_paths=test_paths,
                    documentation_paths=documentation_paths,
                    generated_paths=generated_paths,
                    vendored_paths=vendored_paths,
                ),
            }
        )
    return rows
