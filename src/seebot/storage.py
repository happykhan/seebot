"""Safe storage accounting and pruning within Seebot-owned directories."""

from __future__ import annotations

import shutil
from pathlib import Path


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")


def prune_owned_directory(path: Path) -> int:
    """Remove only the exact caller-supplied Seebot-owned directory."""
    size = directory_size(path)
    if path.exists():
        shutil.rmtree(path)
    return size
