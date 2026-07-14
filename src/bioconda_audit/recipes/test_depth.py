"""Component-first representation of Bioconda recipe test depth."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bioconda_audit import __version__
from bioconda_audit.evidence import (
    audit_code_identity,
    environment_id,
    evidence_path,
    sha256_file,
)
from bioconda_audit.models import CheckResult, EvidencePaths, Status, ToolIdentity


@dataclass(frozen=True)
class RecipeTestFacts:
    has_import_test: bool = False
    has_help_test: bool = False
    has_version_test: bool = False
    has_command_test: bool = False
    uses_test_data: bool = False
    runs_analysis: bool = False
    asserts_output_exists: bool = False
    asserts_output_content: bool = False
    asserts_output_format: bool = False

    @property
    def suggested_depth(self) -> int:
        """Suggest the ordinal level while preserving facts for review."""
        if self.runs_analysis and (self.asserts_output_content or self.asserts_output_format):
            return 4
        if self.runs_analysis and self.uses_test_data:
            return 3
        if self.runs_analysis or (self.has_command_test and self.uses_test_data):
            return 2
        if any(
            (
                self.has_import_test,
                self.has_help_test,
                self.has_version_test,
                self.has_command_test,
            )
        ):
            return 1
        return 0


def write_recipe_test_observation(
    *,
    package_id: str,
    run_id: str,
    recipe_test: dict[str, Any],
    recipes_commit: str,
    recipe_path: str,
    preserved_recipe: Path,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    force: bool = False,
) -> CheckResult:
    check_id = "RECIPE-TEST-DEPTH-001"
    check_dir = evidence_root / run_id / package_id / check_id
    result_path = check_dir / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    check_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = check_dir / "observation.json"
    stderr_path = check_dir / "stderr.txt"
    metadata_path = check_dir / "metadata.json"
    started = datetime.now(UTC)
    clock = time.monotonic()
    observed = {
        "recipes_commit": recipes_commit,
        "recipe_path": recipe_path,
        "recipe_sha256": sha256_file(preserved_recipe),
        "depth": recipe_test["depth"],
        **recipe_test["facts"],
    }
    stdout_path.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    duration = time.monotonic() - clock
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "duration_seconds": duration,
                "environment_id": environment_id(),
                "manifest_sha256": manifest_sha256,
                **audit_code_identity(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = CheckResult(
        run_id=run_id,
        package_id=package_id,
        check_id=check_id,
        domain="recipe",
        status=Status.PASS,
        method="automated_with_manifest",
        expected={"measurement_only": True},
        observed=observed,
        tool=ToolIdentity(name="bcqa", version=__version__),
        command=None,
        started_at=started,
        duration_seconds=duration,
        environment_id=environment_id(),
        config_sha256=sha256_file(config_path),
        evidence=EvidencePaths(
            stdout=evidence_path(stdout_path, evidence_root),
            stderr=evidence_path(stderr_path, evidence_root),
            metadata=evidence_path(metadata_path, evidence_root),
        ),
        notes=recipe_test["notes"],
    )
    result.write(result_path)
    return result
