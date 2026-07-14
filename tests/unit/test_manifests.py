from pathlib import Path

import yaml

from bioconda_audit.manifests import validate_manifest, write_template


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
