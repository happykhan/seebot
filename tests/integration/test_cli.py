from pathlib import Path

from typer.testing import CliRunner

from seebot.cli import app

runner = CliRunner()


def test_help_lists_workflow_groups() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in (
        "cohort",
        "manifest",
        "fixture",
        "survey",
        "cache",
        "history",
        "audit",
        "results",
        "report",
        "batch",
    ):
        assert group in result.stdout


def test_selectable_audit_plan_does_not_execute_tools() -> None:
    result = runner.invoke(app, ["audit", "plan", "--tool", "cutadapt"])
    assert result.exit_code == 0, result.stdout
    assert "cutadapt" in result.stdout
    assert "repository" in result.stdout


def test_repository_only_audit_skips_source_analyzer_setup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("seebot.cli.selected_projects", lambda *args: [])

    def unexpected_setup(*args, **kwargs):
        raise AssertionError("source analyzer setup should not run")

    monkeypatch.setattr("seebot.cli.prepare_analyzer_environment", unexpected_setup)
    result = runner.invoke(
        app,
        ["--output-directory", str(tmp_path), "audit", "run", "--check", "repository"],
    )
    assert result.exit_code == 0, result.stdout


def test_dependency_only_audit_uses_small_analyzer_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("seebot.cli.selected_projects", lambda *args: [])
    calls: list[str] = []

    monkeypatch.setattr(
        "seebot.cli.prepare_dependency_analyzer_environment",
        lambda *args, **kwargs: calls.append("dependencies"),
    )

    def unexpected_source_setup(*args, **kwargs):
        raise AssertionError("full source analyzer setup should not run")

    monkeypatch.setattr("seebot.cli.prepare_analyzer_environment", unexpected_source_setup)
    result = runner.invoke(
        app,
        ["--output-directory", str(tmp_path), "audit", "run", "--check", "dependencies"],
    )

    assert result.exit_code == 0, result.stdout
    assert calls == ["dependencies"]


def test_report_build_overwrites_current_dataset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seebot.cli.build_public_dataset",
        lambda manifest_directory, checks_path: {"projects": [], "schema_version": 2},
    )
    result = runner.invoke(app, ["--output-directory", str(tmp_path), "report", "build"])
    assert result.exit_code == 0, result.stdout
    assert "Prepared web application dataset" in result.stdout
    assert (tmp_path / "web" / "public" / "data" / "dataset.json").exists()
