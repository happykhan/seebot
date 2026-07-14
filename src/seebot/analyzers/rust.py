"""Rust release-source measurements."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seebot.analyzers.command import CommandMeasurement, line_count_parser, run_measurements
from seebot.models import CheckResult


def _cargo_json(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    messages = []
    for line in stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("message"):
            messages.append(row["message"])
    unavailable = any(
        phrase in (stdout + stderr).lower()
        for phrase in (
            "no matching package named",
            "failed to download",
            "failed to get",
            "offline mode",
        )
    )
    return {
        "diagnostic_count": len(messages),
        "build_succeeded": returncode == 0,
        "dependency_cache_available": not unavailable,
        "_audit_status": "UNTESTABLE" if unavailable else None,
    }


def run_rust_analyzers(
    *,
    source_roots: list[Path],
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    force: bool = False,
) -> list[CheckResult]:
    root = next((root for root in source_roots if (root / "Cargo.toml").exists()), source_roots[0])
    cargo = ["--locked", "--offline"]
    specs = [
        CommandMeasurement(
            "RS-CHECK-001",
            "rust",
            "cargo",
            ["cargo", "check", *cargo, "--message-format=json"],
            _cargo_json,
            {0, 101},
            cwd=root,
        ),
        CommandMeasurement(
            "RS-FMT-001",
            "rust",
            "cargo",
            ["cargo", "fmt", "--all", "--", "--check"],
            lambda o, e, r: {"format_check_succeeded": r == 0},
            {0, 1},
            cwd=root,
        ),
        CommandMeasurement(
            "RS-CLIPPY-001",
            "rust",
            "cargo",
            ["cargo", "clippy", *cargo, "--all-targets", "--message-format=json"],
            _cargo_json,
            {0, 101},
            cwd=root,
        ),
        CommandMeasurement(
            "RS-COMPLEXITY-001",
            "rust",
            "rust-code-analysis-cli",
            ["rust-code-analysis-cli", "-p", str(root), "-O", "json"],
            line_count_parser,
        ),
        CommandMeasurement(
            "RS-DOCS-001",
            "rust",
            "cargo",
            ["cargo", "rustdoc", *cargo],
            _cargo_json,
            {0, 101},
            cwd=root,
        ),
        CommandMeasurement(
            "RS-UNSAFE-001",
            "rust",
            "cargo-geiger",
            ["cargo-geiger", *cargo, "--output-format", "Json"],
            line_count_parser,
            {0, 1},
            cwd=root,
        ),
        CommandMeasurement(
            "RS-AUDIT-001",
            "rust",
            "cargo-audit",
            ["cargo-audit", "audit", "--json"],
            lambda o, e, r: json.loads(o or "{}"),
            {0, 1},
            cwd=root,
        ),
    ]
    return run_measurements(
        specs,
        package_id=package_id,
        run_id=run_id,
        evidence_root=evidence_root,
        config_path=config_path,
        manifest_sha256=manifest_sha256,
        language="rust",
        source_roots=source_roots,
        force=force,
    )
