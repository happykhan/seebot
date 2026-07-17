#!/usr/bin/env python3
"""Validate completeness and command safety for one project's evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from seebot.models import CheckResult

UPSTREAM_TEST_RUNNERS = {
    "pytest",
    "py.test",
    "unittest",
    "tox",
    "nox",
    "ctest",
    "prove",
    "cargo-test",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    evidence = root / "evidence" / "current" / args.project
    rows: list[CheckResult] = []
    for path in sorted(evidence.rglob("result.json")):
        rows.append(CheckResult.model_validate_json(path.read_text(encoding="utf-8")))
    if not rows:
        raise RuntimeError(f"No evidence found for {args.project}")
    domains = {row.domain for row in rows}
    missing_domains = {"source", "usage", "robustness"} - domains
    if missing_domains:
        raise RuntimeError(f"Missing evidence domains: {sorted(missing_domains)}")
    manifest: dict[str, Any] = yaml.safe_load(
        (root / f"inputs/manifests/packages/{args.project}.yaml").read_text(encoding="utf-8")
    )
    expected_dates = {
        manifest["repository"]["snapshot_date"],
        *manifest["repository"]["historical_commits"].keys(),
    }
    source_dates = {row.snapshot_date for row in rows if row.domain == "source"}
    if not expected_dates <= source_dates:
        raise RuntimeError(f"Missing source dates: {sorted(expected_dates - source_dates)}")
    for metadata_path in evidence.rglob("metadata.json"):
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        command = payload.get("command")
        if isinstance(command, list) and command:
            executable = Path(str(command[0])).name.lower()
            normalized = (
                f"{executable}-{str(command[1]).lower()}" if len(command) > 1 else executable
            )
            if executable in UPSTREAM_TEST_RUNNERS or normalized in UPSTREAM_TEST_RUNNERS:
                raise RuntimeError(f"Prohibited upstream test command recorded: {command}")
    for row in rows:
        command = row.command
        if command:
            executable = Path(command[0]).name.lower()
            normalized = f"{executable}-{command[1].lower()}" if len(command) > 1 else executable
            if executable in UPSTREAM_TEST_RUNNERS or normalized in UPSTREAM_TEST_RUNNERS:
                raise RuntimeError(f"Prohibited upstream test command recorded: {command}")


if __name__ == "__main__":
    main()
