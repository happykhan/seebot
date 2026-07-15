"""Shared fixture catalogue validation and lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from seebot.evidence import sha256_file

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "fixture-catalog.schema.json"
CATALOGUE_PATH = ROOT / "fixtures" / "catalog.yaml"


def load_catalogue(path: Path = CATALOGUE_PATH) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Fixture catalogue must contain a mapping: {path}")
    return value


def validate_catalogue(path: Path = CATALOGUE_PATH) -> list[str]:
    catalogue = load_catalogue(path)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(catalogue), key=lambda e: list(e.path))
    messages = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]
    seen: set[str] = set()
    root = path.parent
    for fixture in catalogue.get("fixtures", []):
        fixture_id = fixture.get("id")
        if fixture_id in seen:
            messages.append(f"fixtures: duplicate fixture id {fixture_id}")
        seen.add(fixture_id)
        fixture_path = root / str(fixture.get("path", ""))
        if not fixture_path.is_file():
            messages.append(f"{fixture_id}: fixture file does not exist: {fixture_path}")
        elif fixture.get("sha256") != sha256_file(fixture_path):
            messages.append(f"{fixture_id}: fixture hash does not match catalogue")
    return messages


def fixture_index(path: Path = CATALOGUE_PATH) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in load_catalogue(path)["fixtures"]}


def resolve_fixture(fixture_id: str, path: Path = CATALOGUE_PATH) -> Path:
    row = fixture_index(path).get(fixture_id)
    if row is None:
        raise KeyError(f"Unknown fixture id: {fixture_id}")
    return path.parent / str(row["path"])
