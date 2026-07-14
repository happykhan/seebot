"""Reviewed package manifest creation and schema validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "package-manifest.schema.json"


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Manifest must contain a mapping: {path}")
    return value


def validate_manifest(path: Path) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(load_yaml(path)), key=lambda item: list(item.path))
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]


def manifest_template(name: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package": {
            "name": name,
            "cohort_rank": None,
            "download_count": None,
            "download_period": {"start": None, "end": None},
        },
        "bioconda": {
            "recipes_commit": None,
            "recipe_path": f"recipes/{name}",
            "version": None,
            "build": None,
            "subdir": "linux-64",
            "package_url": None,
            "package_sha256": None,
            "primary_executables": [name],
        },
        "classification": {
            "include": True,
            "package_type": "cli_tool",
            "tool_category": None,
            "exclusion_code": None,
            "notes": None,
        },
        "release_source": {
            "source_url": None,
            "source_sha256": None,
            "extracted_root": None,
            "source_ref": None,
        },
        "upstream": {
            "repository_url": None,
            "forge": "unknown",
            "release_tag": None,
            "release_commit": None,
            "default_branch_commit_at_audit": None,
            "mapping_confidence": "unknown",
            "mapping_evidence": None,
        },
        "source_layout": {
            "production_roots": [],
            "test_roots": [],
            "documentation_roots": [],
            "generated_paths": [],
            "vendored_paths": [],
            "excluded_paths": [],
        },
        "cli": {
            "no_argument_policy": "unknown",
            "help_commands": [[name, "--help"]],
            "version_commands": [[name, "--version"]],
            "invalid_option_command": [name, "--definitely-not-a-real-option"],
            "requires_stdin": False,
            "expected_network_access": False,
            "timeout_seconds": 30,
        },
        "functional_test": {
            "status": "not_designed",
            "fixture_directory": None,
            "command": None,
            "expected_outputs": [],
        },
        "curation": {
            "status": "unreviewed",
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        },
    }


def write_template(name: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest_template(name), sort_keys=False), encoding="utf-8")
