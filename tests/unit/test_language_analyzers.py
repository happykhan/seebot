from pathlib import Path

from seebot.analyzers.command import CommandMeasurement, run_measurements
from seebot.analyzers.rust import _cargo_json, cargo_project_root
from seebot.models import Status


def test_missing_language_analyzer_is_untestable(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    spec = CommandMeasurement(
        check_id="PERL-CRITIC-001",
        domain="perl",
        tool="definitely-not-an-installed-seebot-tool",
        command=["definitely-not-an-installed-seebot-tool"],
        parser=lambda stdout, stderr, code: {},
    )
    result = run_measurements(
        [spec],
        package_id="example__1__0__noarch",
        run_id="pilot",
        evidence_root=tmp_path / "evidence",
        config_path=config,
        manifest_sha256="0" * 64,
        language="perl",
        source_roots=[source],
    )[0]
    assert result.status is Status.UNTESTABLE
    assert result.observed["missing_executable"] == spec.tool
    assert "no package judgement" in (result.notes or "")


def test_offline_cargo_cache_miss_is_not_a_source_measurement() -> None:
    observed = _cargo_json(
        "", "error: no matching package named `example` found in offline mode", 101
    )
    assert observed["_audit_status"] == "UNTESTABLE"
    assert observed["dependency_cache_available"] is False


def test_cargo_project_root_can_contain_reviewed_source_root(tmp_path: Path) -> None:
    extracted = tmp_path / "work" / "package" / "source"
    project = extracted / "rasusa-4.1.0"
    source = project / "src"
    source.mkdir(parents=True)
    (project / "Cargo.toml").write_text("[package]\nname = 'rasusa'\n", encoding="utf-8")

    assert cargo_project_root([source]) == project


def test_cargo_project_root_does_not_escape_extracted_source(tmp_path: Path) -> None:
    extracted = tmp_path / "work" / "package" / "source"
    source = extracted / "release" / "src"
    source.mkdir(parents=True)
    (tmp_path / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")

    assert cargo_project_root([source]) == source
