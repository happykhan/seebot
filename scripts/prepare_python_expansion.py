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
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from seebot.analyzers.repository import clone_snapshot
from seebot.runtime.analyzers import prepare_analyzer_environment
from seebot.runtime.pixi import prepare_environment

DEFAULT_PROJECTS = (
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


def load_manifest(repo: Path, project: str) -> tuple[Path, dict[str, Any]]:
    path = repo / "manifests" / "packages" / f"{project}.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed manifest: {path}")
    return path, payload


def prepared_bundle_issues(root: Path, projects: tuple[str, ...]) -> list[str]:
    """Return missing runtime inputs that make an existing bundle unsafe to reuse."""
    required = [
        root / "tools" / "pixi",
        root / "array.tsv",
        root / "run-metadata.json",
        root / "inventory.sha256.json",
        root / "work" / "source-analyzers" / "pixi.lock",
        root / "work" / "source-analyzers" / ".pixi" / "envs" / "default",
    ]
    for project in projects:
        environment = root / "work" / "environments" / project
        required.extend([environment / "pixi.lock", environment / ".pixi" / "envs" / "default"])
    return [str(path.relative_to(root)) for path in required if not path.exists()]


def critical_inventory(root: Path) -> dict[str, str]:
    patterns = (
        "tools/pixi",
        "inputs/**/*",
        "connected/*.json",
        "work/*/pixi.lock",
        "work/environments/*/pixi.lock",
        "array.tsv",
        "run-metadata.json",
    )
    paths = {path for pattern in patterns for path in root.glob(pattern) if path.is_file()}
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(paths)}


def prepare(
    repo: Path,
    shared_root: Path,
    projects: tuple[str, ...] = DEFAULT_PROJECTS,
    *,
    jobs: int = 4,
) -> Path:
    audit_commit = command_output(["git", "rev-parse", "HEAD"], cwd=repo)
    if command_output(["git", "status", "--porcelain"], cwd=repo):
        raise RuntimeError("Commit the tested HPC implementation before canonical preparation")
    final = shared_root / "current"
    if (final / "PREPARED.json").is_file():
        issues = prepared_bundle_issues(final, projects)
        if issues:
            preview = ", ".join(issues[:5])
            suffix = " ..." if len(issues) > 5 else ""
            raise RuntimeError(
                "Existing PREPARED bundle is incomplete and was preserved: " + preview + suffix
            )
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
    (temporary / "array.tsv").write_text(
        "".join(f"{index}\t{project}\n" for index, project in enumerate(projects)),
        encoding="utf-8",
    )
    manifests = [load_manifest(repo, project) for project in projects]
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

    def prepare_snapshot(item: tuple[str, str]) -> None:
        commit, url = item
        snapshot = temporary / "snapshots" / commit
        if snapshot.is_dir():
            observed_commit = command_output(["git", "rev-parse", "HEAD"], cwd=snapshot)
            if observed_commit != commit:
                raise RuntimeError(f"Prepared snapshot commit mismatch: {commit}")
        else:
            clone_snapshot(url, commit, snapshot)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        list(executor.map(prepare_snapshot, sorted(commits.items())))
    os.environ.update(
        SEEBOT_SNAPSHOT_ROOT=str(temporary / "snapshots"),
        SEEBOT_GITHUB_PAYLOAD_ROOT=str(temporary / "connected"),
    )
    cache = temporary / ".seebot-cache" / "pixi"
    prepare_analyzer_environment(temporary / "work" / "source-analyzers", cache)

    def prepare_project(item: tuple[Path, dict[str, Any]]) -> None:
        _, manifest = item
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

    # Pixi creates a large internal Tokio thread pool. Running multiple installs on the
    # shared head node can exhaust its thread allowance even when CPU use is modest.
    for manifest in manifests:
        prepare_project(manifest)
    metadata = {
        "schema_version": 1,
        "prepared_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "audit_commit": audit_commit,
        "host": socket.gethostname(),
        "architecture": platform.machine(),
        "slurm_cluster": "cluster",
        "partition": "short",
        "snapshot_download_jobs": jobs,
        "project_environment_jobs": 1,
        "runtime": command_output([str(pixi), "--version"]),
        "pixi_sha256": sha256(pixi),
        "shared_path": str(final),
        "projects": list(projects),
    }
    (temporary / "run-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    inventory = critical_inventory(temporary)
    (temporary / "inventory.sha256.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    issues = prepared_bundle_issues(temporary, projects)
    if issues:
        raise RuntimeError("Prepared bundle is incomplete: " + ", ".join(issues))
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
    parser.add_argument(
        "--tool",
        action="append",
        help="Project id to include in the prepared Slurm array. May be repeated.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Concurrent source-download workers; Pixi environments are built serially.",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    projects = tuple(args.tool) if args.tool else DEFAULT_PROJECTS
    print(prepare(args.repo.resolve(), args.shared_root.resolve(), projects, jobs=args.jobs))


if __name__ == "__main__":
    main()
