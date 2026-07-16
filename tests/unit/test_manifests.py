import json
from pathlib import Path

import yaml

from seebot.manifests import validate_manifest, write_template

ROOT = Path(__file__).resolve().parents[2]


def test_generated_manifest_validates(tmp_path: Path) -> None:
    path = tmp_path / "example.yaml"
    write_template("example-tool", path)
    assert validate_manifest(path) == []


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "example.yaml"
    write_template("example-tool", path)
    data = yaml.safe_load(path.read_text())
    data["guessed_quality_score"] = 99
    path.write_text(yaml.safe_dump(data))
    errors = validate_manifest(path)
    assert any("Additional properties are not allowed" in error for error in errors)


def test_selected_history_matches_curated_manifests() -> None:
    history = set(
        json.loads((ROOT / "data/cohort/selected-history.json").read_text(encoding="utf-8"))
    )
    manifests = {path.stem for path in (ROOT / "manifests/packages").glob("*.yaml")}
    assert history == manifests
