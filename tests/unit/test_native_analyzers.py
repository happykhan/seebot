from pathlib import Path
from typing import Any
from unittest.mock import Mock

from pytest import MonkeyPatch

from seebot.analyzers.native import (
    _cppcheck_parser,
    _cython_lint_parser,
    _perlcritic_parser,
    run_non_python_native_analyzers,
)
from seebot.analyzers.python import run_python_analyzers
from seebot.analyzers.source import run_source_observations
from seebot.models import Status


def test_cppcheck_keeps_native_rule_ids_and_security_filter() -> None:
    xml = (
        '<results><errors><error id="nullPointer" severity="error" />'
        '<error id="unusedFunction" severity="style" /></errors></results>'
    )
    lint, lint_status = _cppcheck_parser(100, security_only=False)("", xml, 0)
    security, security_status = _cppcheck_parser(100, security_only=True)("", xml, 0)
    assert lint_status is Status.OBSERVED
    assert lint["finding_count"] == 2
    assert security_status is Status.OBSERVED
    assert security["finding_count"] == 1
    assert security["rules"][0]["rule"] == "nullPointer"


def test_cppcheck_accepts_xml_with_stderr_preamble() -> None:
    stderr = (
        "Checking source file...\n"
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<results version="2"><errors>'
        '<error id="unusedFunction" severity="style" />'
        "</errors></results>\n"
    )
    observed, status = _cppcheck_parser(100, security_only=False)(
        stdout="", stderr=stderr, returncode=0
    )
    assert status is Status.OBSERVED
    assert observed["finding_count"] == 1
    assert observed["rules"][0]["rule"] == "unusedFunction"


def test_perlcritic_keeps_policy_and_severity() -> None:
    output = "Variables::ProhibitPunctuationVars~|~message~|~3~|~4~|~2\n"
    observed, status = _perlcritic_parser(200)(output, "", 2)
    assert status is Status.OBSERVED
    assert observed["rules"][0]["rule"] == "Variables::ProhibitPunctuationVars"
    assert observed["findings_per_kloc"] == 5.0


def test_cython_lint_keeps_native_rule_ids() -> None:
    observed, status = _cython_lint_parser(100)(
        "src/tool.pyx:2:4: E225 missing whitespace\n", "", 1
    )
    assert status is Status.OBSERVED
    assert observed["rules"][0]["rule"] == "E225"
    assert observed["findings_per_kloc"] == 10.0


def test_pmd_uses_file_list_instead_of_expanding_command_line(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    source = checkout / "src/main/java/example/Main.java"
    source.parent.mkdir(parents=True)
    source.write_text("class Main {}\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "seebot.analyzers.native._run_native",
        lambda **kwargs: calls.append(kwargs) or Mock(),
    )

    run_non_python_native_analyzers(
        environment=Mock(),
        manifest={"project": {"id": "example"}},
        checkout=checkout,
        language="java",
        files=[source],
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_root=tmp_path / "config",
        snapshot_date="2026-07-17",
        snapshot_commit="abc",
    )

    assert len(calls) == 2
    for call in calls:
        assert "--file-list=/work/source-files.txt" in call["command"]
        assert call["input_files"] == ["/source/src/main/java/example/Main.java"]
        assert str(source) not in call["command"]


def test_ruff_disables_cache_for_read_only_source_mount(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    source = checkout / "tool.py"
    checkout.mkdir()
    source.write_text("print('ok')\n")
    commands: list[list[str]] = []

    def capture_command(**kwargs: Any) -> Mock:
        commands.append(kwargs["command"])
        return Mock()

    monkeypatch.setattr("seebot.analyzers.python._run_native", capture_command)

    run_python_analyzers(
        environment=Mock(),
        checkout=checkout,
        files=[source],
        project_id="example",
        run_id="run",
        evidence_root=tmp_path / "evidence",
        config_root=tmp_path / "config",
    )

    ruff_command = commands[0]
    assert ruff_command[:3] == ["ruff", "check", "--no-cache"]


def test_pylint_uses_configured_parallel_workers(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    checkout = tmp_path / "checkout"
    source = checkout / "tool.py"
    checkout.mkdir()
    source.write_text("print('ok')\n", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setenv("SEEBOT_ANALYZER_JOBS", "8")
    monkeypatch.setattr(
        "seebot.analyzers.python._run_native",
        lambda **kwargs: commands.append(kwargs["command"]) or Mock(),
    )

    run_python_analyzers(
        environment=Mock(),
        checkout=checkout,
        files=[source],
        project_id="example",
        run_id="run",
        evidence_root=tmp_path / "evidence",
        config_root=tmp_path / "config",
    )

    pylint_command = next(command for command in commands if command[0] == "pylint")
    assert pylint_command[1:4] == ["--output-format=json", "--jobs", "8"]


def test_python_analyzers_record_zero_findings_without_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    config = tmp_path / "config"
    checkout.mkdir()
    config.mkdir()
    (config / "rubric.yaml").write_text("rubric: test\n", encoding="utf-8")

    def fail_if_invoked(**kwargs: Any) -> Mock:
        raise AssertionError("native analyzer should not run with no files")

    monkeypatch.setattr("seebot.analyzers.python._run_native", fail_if_invoked)

    results = run_python_analyzers(
        environment=Mock(),
        checkout=checkout,
        files=[],
        project_id="example",
        run_id="run",
        evidence_root=tmp_path / "evidence",
        config_root=config,
        force=True,
    )

    assert len(results) == 4
    assert {result.status for result in results} == {Status.OBSERVED}
    assert all(result.observed.get("finding_count", 0) == 0 for result in results)


def test_historical_source_skips_native_analyzers(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    structural = Mock()
    monkeypatch.setattr(
        "seebot.analyzers.source.run_structural_observations", lambda **kwargs: [structural]
    )

    def unexpected_native(**kwargs: Any) -> Mock:
        raise AssertionError("historical snapshots should not run native analyzers")

    monkeypatch.setattr("seebot.analyzers.source.run_python_analyzers", unexpected_native)

    results = run_source_observations(
        manifest_path=tmp_path / "manifest.yaml",
        manifest={"project": {"id": "example"}, "source": {"language_roots": {"python": []}}},
        checkout=tmp_path,
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_root=tmp_path / "config",
        snapshot_date="2025-07-01",
        snapshot_commit="abc",
        analyzer_environment=Mock(),
        include_native=False,
    )

    assert results == [structural]
