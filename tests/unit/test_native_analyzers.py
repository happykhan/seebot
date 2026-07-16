from pathlib import Path
from typing import Any
from unittest.mock import Mock

from pytest import MonkeyPatch

from seebot.analyzers.native import _cppcheck_parser, _cython_lint_parser, _perlcritic_parser
from seebot.analyzers.python import run_python_analyzers
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
