#!/usr/bin/env python3
"""Prepare connected inputs and observations for the Python Slurm expansion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from seebot.analyzers.repository import clone_snapshot
from seebot.runtime.analyzers import (
    prepare_analyzer_environment,
    prepare_dependency_analyzer_environment,
)
from seebot.runtime.pixi import prepare_environment

PROJECTS = (
    "harpy",
    "deeptools",
    "htseq",
    "snakemake-minimal",
    "dxpy",
    "prophyle",
    "pyfaidx",
    "sepp",
    "anarci",
    "metaphlan",
    "dendropy",
    "samsift",
    "pasta",
    "crisprme",
    "itsxpress",
    "scanpy-scripts",
    "zdb",
    "cooler",
    "rgi",
    "igv-reports",
)


def command_output(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(
        command, cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(b"F")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif path.is_dir():
            digest.update(b"D")
        digest.update(b"\0")
    return digest.hexdigest()


def load_manifest(repo: Path, project: str) -> tuple[Path, dict[str, Any]]:
    path = repo / "manifests" / "packages" / f"{project}.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed manifest: {path}")
    return path, payload


def critical_inventory(root: Path) -> dict[str, str]:
    patterns = (
        "tools/pixi",
        "inputs/**/*",
        "snapshots/*/.git/HEAD",
        "snapshots/*/.git/index",
        "snapshots/*.sha256",
        "connected/*.json",
        "work/*/pixi.lock",
        "work/environments/*/pixi.lock",
        "array.json",
        "array.tsv",
        "run-metadata.json",
    )
    paths = {path for pattern in patterns for path in root.glob(pattern) if path.is_file()}
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(paths)}


def prepare(repo: Path, shared_root: Path) -> Path:
    audit_commit = command_output(["git", "rev-parse", "HEAD"], cwd=repo)
    if command_output(["git", "status", "--porcelain"], cwd=repo):
        raise RuntimeError("Commit the tested HPC implementation before canonical preparation")
    final = shared_root / "current"
    if (final / "PREPARED.json").is_file():
        return final
    temporary = final
    temporary.mkdir(parents=True, exist_ok=True)
    pixi_source = Path("/users/aanensen/rva470/.pixi/bin/pixi")
    pixi = temporary / "tools" / "pixi"
    pixi.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pixi_source, pixi)
    os.environ.update(SEEBOT_CONTAINER_RUNTIME="native", SEEBOT_PIXI_EXECUTABLE=str(pixi))
    for source in ("config", "fixtures", "manifests", "schemas"):
        shutil.copytree(repo / source, temporary / "inputs" / source, dirs_exist_ok=True)
    history_target = temporary / "inputs" / "data" / "cohort"
    history_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "data/cohort/selected-history.json", history_target)
    array = [{"index": index, "project_id": project} for index, project in enumerate(PROJECTS)]
    (temporary / "array.json").write_text(json.dumps(array, indent=2) + "\n", encoding="utf-8")
    (temporary / "array.tsv").write_text(
        "".join(f"{row['index']}\t{row['project_id']}\n" for row in array), encoding="utf-8"
    )
    manifests = [load_manifest(repo, project) for project in PROJECTS]
    commits: dict[str, str] = {}
    for _, manifest in manifests:
        repository = manifest["repository"]
        snapshot_commits = [
            repository["snapshot_commit"],
            *(repository["historical_commits"] or {}).values(),
        ]
        for commit in snapshot_commits:
            if commit:
                commits[str(commit)] = str(repository["url"])
    for commit, url in sorted(commits.items()):
        snapshot = temporary / "snapshots" / commit
        tree_hash_path = temporary / "snapshots" / f"{commit}.sha256"
        if snapshot.is_dir():
            observed_commit = command_output(["git", "rev-parse", "HEAD"], cwd=snapshot)
            if observed_commit != commit:
                raise RuntimeError(f"Prepared snapshot commit mismatch: {commit}")
            observed_tree_hash = (
                tree_hash_path.read_text(encoding="utf-8").strip()
                if tree_hash_path.is_file()
                else tree_sha256(snapshot)
            )
        else:
            snapshot = clone_snapshot(url, commit, snapshot)
            observed_tree_hash = tree_sha256(snapshot)
        tree_hash_path.write_text(observed_tree_hash + "\n", encoding="utf-8")
    os.environ.update(
        SEEBOT_SNAPSHOT_ROOT=str(temporary / "snapshots"),
        SEEBOT_GITHUB_PAYLOAD_ROOT=str(temporary / "connected"),
    )
    cache = temporary / ".seebot-cache" / "pixi"
    prepare_analyzer_environment(temporary / "work" / "source-analyzers", cache)
    prepare_dependency_analyzer_environment(temporary / "work" / "dependency-analyzers", cache)
    for _, manifest in manifests:
        installation = manifest["installation"]
        prepare_environment(
            temporary / "work" / "environments" / manifest["project"]["id"],
            cache_root=cache,
            project_id=manifest["project"]["id"],
            package_name=installation["artifact"],
            version=str(installation["version"]),
            build=installation["build"],
            channels=installation["channels"],
        )
    metadata = {
        "schema_version": 1,
        "prepared_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "audit_commit": audit_commit,
        "host": socket.gethostname(),
        "architecture": platform.machine(),
        "slurm_cluster": "cluster",
        "partition": "short",
        "runtime": command_output([str(pixi), "--version"]),
        "pixi_sha256": sha256(pixi),
        "shared_path": str(final),
        "projects": list(PROJECTS),
    }
    (temporary / "run-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    inventory = critical_inventory(temporary)
    (temporary / "inventory.sha256.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    (temporary / "PREPARED.json").write_text(
        json.dumps({"audit_commit": audit_commit, "inventory_entries": len(inventory)}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--shared-root", type=Path, default=Path("/well/aanensen/users/rva470/seebot-hpc")
    )
    args = parser.parse_args()
    print(prepare(args.repo.resolve(), args.shared_root.resolve()))


if __name__ == "__main__":
    main()
