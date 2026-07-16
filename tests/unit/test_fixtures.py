from pathlib import Path

import yaml

from seebot.fixtures import resolve_fixture, validate_catalogue


def test_repository_fixture_catalogue_validates() -> None:
    assert validate_catalogue() == []
    assert resolve_fixture("bad-empty").stat().st_size == 0
    assert resolve_fixture("empty-fastq").stat().st_size == 0
    assert resolve_fixture("empty-fasta").stat().st_size == 0
    assert "@HD" in resolve_fixture("empty-header-only-sam").read_text(encoding="utf-8")


def test_fixture_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.txt"
    fixture.write_text("changed\n", encoding="utf-8")
    catalogue = {
        "schema_version": 1,
        "catalogue_id": "test",
        "fixtures": [
            {
                "id": "fixture",
                "path": "fixture.txt",
                "format": "text",
                "validity": "valid",
                "intent": "test",
                "sha256": "0" * 64,
                "provenance": "test",
                "licence": "CC0-1.0",
            }
        ],
    }
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(catalogue), encoding="utf-8")
    assert any("hash does not match" in error for error in validate_catalogue(path))
