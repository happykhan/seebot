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


def test_history_includes_current_and_historical_source(tmp_path: Path, monkeypatch) -> None:
    manifest = {"project": {"id": "example"}}
    monkeypatch.setattr(
        "seebot.cli.selected_projects", lambda *args: [(tmp_path / "example.yaml", manifest)]
    )
    monkeypatch.setattr("seebot.cli.prepare_analyzer_environment", lambda *args: object())
    calls: list[tuple[bool, bool]] = []

    def record_source(**kwargs):
        calls.append((kwargs["include_history"], kwargs["include_source"]))
        return []

    monkeypatch.setattr("seebot.cli.run_repository_and_source", record_source)
    result = runner.invoke(
        app,
        ["--output-directory", str(tmp_path), "audit", "run", "--check", "history"],
    )

    assert result.exit_code == 0, result.stdout
    assert calls == [(True, True)]


def test_named_cli_check_dispatches_usage_runner(tmp_path: Path, monkeypatch) -> None:
    manifest = {"project": {"id": "example"}}
    monkeypatch.setattr(
        "seebot.cli.selected_projects", lambda *args: [(tmp_path / "example.yaml", manifest)]
    )
    calls: list[set[str]] = []

    def record_usage(*args, **kwargs):
        calls.append(kwargs["checks"])
        return []

    monkeypatch.setattr("seebot.cli.run_project_usage", record_usage)
    result = runner.invoke(
        app,
        [
            "--output-directory",
            str(tmp_path),
            "audit",
            "run",
            "--check",
            "CLI-HELP-001",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert calls == [{"CLI-HELP-001"}]


def test_report_build_overwrites_current_dataset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seebot.cli.build_public_dataset",
        lambda manifest_directory, checks_path, evidence_base=None: {
            "projects": [],
            "schema_version": 2,
        },
    )
    result = runner.invoke(app, ["--output-directory", str(tmp_path), "report", "build"])
    assert result.exit_code == 0, result.stdout
    assert "Prepared web application dataset" in result.stdout
    assert (tmp_path / "web" / "public" / "data" / "dataset.json").exists()
