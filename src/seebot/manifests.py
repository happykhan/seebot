"""Reviewed project manifest creation and schema validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "project-manifest.schema.json"


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
        "schema_version": 2,
        "project": {
            "id": name,
            "name": name,
            "description": None,
            "primary_category": None,
            "tags": [],
            "include": True,
            "exclusion_code": None,
        },
        "repository": {
            "url": None,
            "forge": "unknown",
            "snapshot_date": "2026-07-01",
            "snapshot_commit": None,
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
            "adapter": "pixi",
            "artifact": name,
            "version": None,
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
        "valid_run": {
            "status": "not_designed",
            "fixture_ids": [],
            "command": None,
            "expected_outputs": [],
            "timeout_seconds": 300,
        },
        "robustness": {
            name: {
                "applicability": "unknown",
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
            "notes": None,
        },
    }


def write_template(name: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest_template(name), sort_keys=False), encoding="utf-8")
