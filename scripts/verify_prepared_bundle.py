#!/usr/bin/env python3
"""Verify immutable inputs needed by one Slurm array task."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    required = {"tools/pixi", f"inputs/manifests/packages/{args.project}.yaml"}
    manifest_path = root / f"inputs/manifests/packages/{args.project}.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    commits = [
        manifest["repository"]["snapshot_commit"],
        *(manifest["repository"]["historical_commits"] or {}).values(),
    ]
    required.update(f"snapshots/{commit}/.git/HEAD" for commit in commits if commit)
    required.update(f"snapshots/{commit}.sha256" for commit in commits if commit)
    missing = sorted(required - set(inventory))
    if missing:
        raise RuntimeError(f"Required inventory entries are missing: {missing}")
    for relative in sorted(required):
        path = root / relative
        observed = sha256(path)
        if observed != inventory[relative]:
            raise RuntimeError(f"Prepared input hash mismatch: {relative}")
    environment = root / "work" / "environments" / args.project
    if (
        not (environment / "pixi.lock").is_file()
        or not (environment / ".pixi/envs/default").is_dir()
    ):
        raise RuntimeError(f"Prepared project environment is incomplete: {environment}")


if __name__ == "__main__":
    main()
