"""Language-neutral source size and duplication measurements."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from seebot.analyzers.command import CommandMeasurement, run_measurements
from seebot.models import CheckResult


def _json(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    value = json.loads(stdout or "{}")
    return value if isinstance(value, dict) else {"records": value}


def _jscpd(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    text = stdout + stderr
    percent = re.search(r"(?:duplicated lines|duplication)[^\d]*(\d+(?:\.\d+)?)%", text, re.I)
    clones = re.search(r"Found\s+(\d+)\s+clones?", text, re.I)
    return {
        "duplication_percent": float(percent.group(1)) if percent else None,
        "clone_count": int(clones.group(1)) if clones else None,
    }


def run_universal_analyzers(
    *,
    source_roots: list[Path],
    language: str,
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    force: bool = False,
) -> list[CheckResult]:
    roots = [str(root) for root in source_roots]
    specs = [
        CommandMeasurement(
            f"SRC-{language.upper()}-SLOC-001",
            "source",
            "tokei",
            ["tokei", "--output", "json", *roots],
            _json,
        ),
        CommandMeasurement(
            f"SRC-{language.upper()}-DUPLICATION-001",
            "source",
            "jscpd",
            ["jscpd", "--reporters", "console", *roots],
            _jscpd,
            {0, 1},
        ),
    ]
    return run_measurements(
        specs,
        package_id=package_id,
        run_id=run_id,
        evidence_root=evidence_root,
        config_path=config_path,
        manifest_sha256=manifest_sha256,
        language=language,
        source_roots=source_roots,
        force=force,
    )
