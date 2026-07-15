"""Reviewed project manifest creation and schema validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "project-manifest.schema.json"
REVIEW_SCHEMA_PATH = ROOT / "schemas" / "manual-review.schema.json"


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Manifest must contain a mapping: {path}")
    return value


def validate_manifest(path: Path) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(load_yaml(path)), key=lambda item: list(item.path))
    messages = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]
    manifest = load_yaml(path)
    if not messages and manifest["curation"]["status"] == "reviewed":
        review_schema = json.loads(REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
        review_validator = Draft202012Validator(review_schema, format_checker=FormatChecker())
        expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        reviewer_ids: set[str] = set()
        for field in ("curator_record", "reviewer_record"):
            relative = manifest["curation"].get(field)
            review_path = ROOT / relative if relative else None
            if review_path is None or not review_path.exists():
                messages.append(f"curation/{field}: review record does not exist")
                continue
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review_errors = sorted(
                review_validator.iter_errors(review), key=lambda item: list(item.path)
            )
            messages.extend(
                f"curation/{field}/"
                f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
                f"{error.message}"
                for error in review_errors
            )
            if review.get("project_id") != manifest["project"]["id"]:
                messages.append(f"curation/{field}: project_id does not match manifest")
            if review.get("assessment", {}).get("manifest_sha256") != expected_hash:
                messages.append(f"curation/{field}: manifest_sha256 does not match manifest")
            reviewer_ids.add(str(review.get("reviewer_id")))
        if len(reviewer_ids) != 2:
            messages.append("curation: curator and reviewer identities must be distinct")
    return messages


def manifest_template(name: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "project": {
            "id": name,
            "name": name,
            "description": None,
            "primary_language": "python",
            "primary_category": None,
            "tags": [],
            "include": True,
            "exclusion_code": None,
        },
        "repository": {
            "id": name,
            "url": None,
            "forge": "unknown",
            "snapshot_date": "2026-07-01",
            "snapshot_commit": None,
            "historical_commits": {
                year: None
                for year in (
                    "2021-07-01",
                    "2022-07-01",
                    "2023-07-01",
                    "2024-07-01",
                    "2025-07-01",
                )
            },
            "archived": None,
        },
        "discovery": {
            "source": "bioconda",
            "package_name": name,
            "rank": None,
            "download_count": None,
            "download_period": {"start": "2025-07-01", "end": "2026-06-30"},
        },
        "installation": {
            "id": f"pixi-{name}",
            "adapter": "pixi",
            "artifact": name,
            "version": None,
            "build": None,
            "subdir": "unknown",
            "artifact_url": None,
            "artifact_sha256": None,
            "channels": ["conda-forge", "bioconda"],
            "platform": "linux-64",
        },
        "source": {
            "production_roots": [],
            "language_roots": {},
            "generated_paths": [],
            "vendored_paths": [],
            "excluded_paths": [],
        },
        "interfaces": {
            "primary": name,
            "executables": [name],
            "help_commands": [[name, "--help"]],
            "version_commands": [[name, "--version"]],
            "no_argument_policy": "unknown",
            "stdin_support": "unknown",
            "stdout_support": "unknown",
        },
        "streams": {
            "applicability": "unknown",
            "reason": None,
            "command": None,
            "fixture_ids": [],
            "stdin_fixture_id": None,
            "expect_stdout": False,
            "stdout_parser": None,
            "timeout_seconds": 300,
        },
        "valid_run": {
            "status": "not_designed",
            "untestable_reason": None,
            "fixture_ids": [],
            "command": None,
            "expected_outputs": [],
            "expect_stdout": False,
            "stdout_parser": None,
            "timeout_seconds": 300,
        },
        "robustness": {
            name: {
                "applicability": "unknown",
                "reason": None,
                "command": None,
                "fixture_id": None,
                "diagnostic_expectation": "unknown",
            }
            for name in (
                "missing_input",
                "empty_input",
                "malformed_input",
                "wrong_format",
                "invalid_option",
                "invalid_value",
                "unwritable_output",
            )
        },
        "curation": {
            "status": "unreviewed",
            "curator": None,
            "reviewer": None,
            "reviewed_at": None,
            "curator_record": None,
            "reviewer_record": None,
            "notes": None,
        },
    }


def write_template(name: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest_template(name), sort_keys=False), encoding="utf-8")
