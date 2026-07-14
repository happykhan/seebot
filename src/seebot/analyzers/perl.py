"""Perl release-source measurements."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from seebot.analyzers.command import CommandMeasurement, run_measurements
from seebot.models import CheckResult


def _critic(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    rows = [line for line in (stdout + stderr).splitlines() if line.strip()]
    severities: dict[str, int] = {}
    for row in rows:
        match = re.search(r"severity\s+(\d)", row, re.I)
        key = match.group(1) if match else "UNKNOWN"
        severities[key] = severities.get(key, 0) + 1
    return {"finding_count": len(rows), "findings_by_severity": severities}


def _json(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return {"output": stdout.strip() or stderr.strip()}
    return value if isinstance(value, dict) else {"records": value}


def run_perl_analyzers(
    *,
    source_roots: list[Path],
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    force: bool = False,
) -> list[CheckResult]:
    files = sorted(
        path
        for root in source_roots
        for pattern in ("*.pl", "*.pm")
        for path in root.rglob(pattern)
    )
    paths = [str(path) for path in files]
    specs = [
        CommandMeasurement(
            "PERL-COMPILE-001",
            "perl",
            "perl",
            [
                "perl",
                "-e",
                "for $f (@ARGV) { system($^X, '-c', $f) == 0 or $bad = 1 } exit($bad || 0)",
                *paths,
            ],
            lambda o, e, r: {"file_count": len(files), "syntax_check_succeeded": r == 0},
        ),
        CommandMeasurement(
            "PERL-CRITIC-001",
            "perl",
            "perlcritic",
            ["perlcritic", "--profile", str(config_path), *paths],
            _critic,
            set(range(0, 6)),
        ),
        CommandMeasurement(
            "PERL-COMPLEXITY-001", "perl", "countperl", ["countperl", *paths], _json
        ),
        CommandMeasurement(
            "PERL-POD-001",
            "perl",
            "pod_cover",
            ["pod_cover", *paths],
            lambda o, e, r: {"report": (o or e).strip()},
        ),
    ]
    return run_measurements(
        specs,
        package_id=package_id,
        run_id=run_id,
        evidence_root=evidence_root,
        config_path=config_path,
        manifest_sha256=manifest_sha256,
        language="perl",
        source_roots=source_roots,
        force=force,
    )
