from pathlib import Path

from typer.testing import CliRunner

from bioconda_audit.cli import app

runner = CliRunner()


def test_help_lists_workflow_groups() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in ("cohort", "manifest", "recipe", "source", "audit", "results", "report", "batch"):
        assert group in result.stdout


def test_fixture_cli_audit_and_normalization(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "cli-tools" / "healthy-tool.yaml"
    audit = runner.invoke(
        app,
        ["--output-directory", str(tmp_path), "--run-id", "fixture", "audit", "cli", str(fixture)],
    )
    assert audit.exit_code == 0, audit.stdout
    assert "PASS" in audit.stdout
    normalize = runner.invoke(
        app,
        ["--output-directory", str(tmp_path), "--run-id", "fixture", "results", "normalize"],
    )
    assert normalize.exit_code == 0, normalize.stdout
    assert (tmp_path / "results" / "fixture" / "checks.json").exists()
