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


def compact_run_evidence(evidence_root: Path, run_id: str, *, delete: bool) -> tuple[int, int]:
    """Remove one beta run's per-check intermediates after summaries are built."""
    run_root = (evidence_root / run_id).resolve()
    if not run_root.is_dir():
        raise ValueError(f"No evidence run found at {run_root}")
    files = [path for path in run_root.rglob("*") if path.is_file() or path.is_symlink()]
    if not any(path.name == "result.json" for path in files):
        raise ValueError(f"No result records found under {run_root}")
    size = sum(path.lstat().st_size for path in files)
    if delete:
        shutil.rmtree(run_root)
    return len(files), size
