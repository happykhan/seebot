"""Component-first representation of Bioconda recipe test depth."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot import __version__
from seebot.evidence import (
    audit_code_identity,
    environment_id,
    evidence_path,
    sha256_file,
)
from seebot.models import CheckResult, EvidencePaths, ResultKind, Status, ToolIdentity


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


def suggest_recipe_test_facts(recipe_text: str) -> RecipeTestFacts:
    """Suggest auditable test facts from the preserved recipe text.

    This deliberately does not claim to render a Bioconda recipe. It only
    recognizes high-confidence signals in the ``test`` block so a curator can
    see when reviewed facts and preserved source disagree.
    """
    match = re.search(
        r"(?ms)^test:\s*\n(?P<body>.*?)(?=^[a-zA-Z][\w-]*:\s*(?:#.*)?$|\Z)",
        recipe_text,
    )
    if not match:
        return RecipeTestFacts()
    body = match.group("body")
    commands_match = re.search(
        r"(?ms)^\s{2,}commands:\s*\n(?P<body>.*?)(?=^\s{2,}[\w-]+:\s*(?:#.*)?$|\Z)",
        body,
    )
    commands = commands_match.group("body") if commands_match else ""
    lowered = commands.lower()
    command_lines = [
        line.strip()[1:].strip() for line in commands.splitlines() if line.strip().startswith("-")
    ]
    assertion_text = "\n".join(command_lines).lower()
    has_import = bool(re.search(r"(?m)^\s{2,}imports:\s*$", body))
    has_command = bool(command_lines)
    return RecipeTestFacts(
        has_import_test=has_import,
        has_help_test=bool(re.search(r"(?:^|\s)--help(?:\s|$)", lowered)),
        has_version_test=bool(
            re.search(r"(?:^|\s)--version(?:\s|$)", lowered)
            or re.search(r"\bversion\b", assertion_text)
        ),
        has_command_test=has_command,
        uses_test_data=bool(
            re.search(
                r"\b(test|tests|fixture|example)[-_/\.\w]*\."
                r"(fa|fasta|fq|fastq|bam|sam|vcf|csv|tsv|txt|sig)\b",
                lowered,
            )
        ),
        runs_analysis=bool(
            command_lines
            and not all(
                re.search(r"--(?:help|version)\b|\binfo\b", line.lower()) for line in command_lines
            )
        ),
        asserts_output_exists=bool(re.search(r"\btest\s+-[efsd]\b|\[\s+-[efsd]\s+", lowered)),
        asserts_output_content=bool(re.search(r"\b(grep|diff|cmp)\b", lowered)),
        asserts_output_format=bool(re.search(r"\b(file|jq|xmllint|jsonschema)\b", lowered)),
    )


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
    suggested = suggest_recipe_test_facts(preserved_recipe.read_text(encoding="utf-8"))
    suggested_facts = {
        name: getattr(suggested, name) for name in RecipeTestFacts.__dataclass_fields__
    }
    reviewed_facts = recipe_test["facts"]
    mismatches = {
        name: {"reviewed": reviewed_facts[name], "suggested": value}
        for name, value in suggested_facts.items()
        if reviewed_facts[name] != value
    }
    observed = {
        "recipes_commit": recipes_commit,
        "recipe_path": recipe_path,
        "recipe_sha256": sha256_file(preserved_recipe),
        "depth": recipe_test["depth"],
        **reviewed_facts,
        "source_text_suggestion": {
            "depth": suggested.suggested_depth,
            "facts": suggested_facts,
            "mismatches": mismatches,
            "requires_review": bool(mismatches),
            "method_limit": "high-confidence text signals only; not a rendered recipe",
        },
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
        result_kind=ResultKind.MEASUREMENT,
        method="automated_with_manifest",
        expected={"measurement_only": True},
        observed=observed,
        tool=ToolIdentity(name="seebot", version=__version__),
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
