#!/usr/bin/env python3
"""Verify immutable inputs needed by one Slurm array task."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory = json.loads((root / "inventory.sha256.json").read_text(encoding="utf-8"))
    required = {
        f"inputs/manifests/packages/{args.project}.yaml",
        "work/source-analyzers/pixi.lock",
        f"work/environments/{args.project}/pixi.lock",
    }
    manifest_path = root / f"inputs/manifests/packages/{args.project}.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    commits = [
        manifest["repository"]["snapshot_commit"],
        *(manifest["repository"]["historical_commits"] or {}).values(),
    ]
    missing = sorted(required - set(inventory))
    if missing:
        raise RuntimeError(f"Required inventory entries are missing: {missing}")
    missing_paths = sorted(relative for relative in required if not (root / relative).is_file())
    if missing_paths:
        raise RuntimeError(f"Prepared input files are missing: {missing_paths}")
    pixi = root / "tools" / "pixi"
    if not pixi.is_file() or not pixi.stat().st_mode & 0o111:
        raise RuntimeError(f"Prepared Pixi executable is missing or not executable: {pixi}")
    for relative in sorted(required):
        path = root / relative
        observed = sha256(path)
        if observed != inventory[relative]:
            raise RuntimeError(f"Prepared input hash mismatch: {relative}")
    for commit in filter(None, commits):
        snapshot = root / "snapshots" / commit
        if not snapshot.is_dir():
            raise RuntimeError(f"Prepared snapshot is missing: {snapshot}")
        observed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=snapshot,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if observed != commit:
            raise RuntimeError(f"Prepared snapshot commit mismatch: {commit} != {observed}")
    environment = root / "work" / "environments" / args.project
    if (
        not (environment / "pixi.lock").is_file()
        or not (environment / ".pixi/envs/default").is_dir()
    ):
        raise RuntimeError(f"Prepared project environment is incomplete: {environment}")
    analyzer = root / "work" / "source-analyzers"
    if not (analyzer / "pixi.lock").is_file() or not (analyzer / ".pixi/envs/default").is_dir():
        raise RuntimeError(f"Prepared source analyzer environment is incomplete: {analyzer}")


if __name__ == "__main__":
    main()
