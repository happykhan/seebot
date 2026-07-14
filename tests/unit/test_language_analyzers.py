from pathlib import Path

from seebot.analyzers.command import CommandMeasurement, run_measurements
from seebot.analyzers.rust import _cargo_json
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
