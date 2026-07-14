from pathlib import Path
from sys import executable

from seebot.evidence import ProbeSpec, run_probe
from seebot.models import Status


def test_non_matching_exit_code_is_package_fail(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    result = run_probe(
        ProbeSpec(
            "fixture__1__0__noarch",
            "CLI-HELP-001",
            [executable, "-c", "raise SystemExit(7)"],
            [0],
            5,
        ),
        run_id="test",
        evidence_root=tmp_path / "evidence",
        config_path=config,
    )
    assert result.status is Status.FAIL
    assert result.observed["exit_code"] == 7
    assert result.evidence.stdout.startswith("evidence/test/")
    assert not Path(result.evidence.stdout).is_absolute()


def test_missing_executable_is_audit_error(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    result = run_probe(
        ProbeSpec("fixture__1__0__noarch", "CLI-HELP-001", ["does-not-exist-seebot"], [0], 5),
        run_id="test",
        evidence_root=tmp_path / "evidence",
        config_path=config,
    )
    assert result.status is Status.ERROR
    assert result.observed["audit_error"] == "FileNotFoundError"


def test_resume_preserves_completed_evidence(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    spec = ProbeSpec(
        "fixture__1__0__noarch",
        "CLI-HELP-001",
        [executable, "-c", "print('first')"],
        [0],
        5,
    )
    first = run_probe(spec, run_id="test", evidence_root=tmp_path / "evidence", config_path=config)
    second = run_probe(
        ProbeSpec(spec.package_id, spec.check_id, [executable, "-c", "print('second')"], [0], 5),
        run_id="test",
        evidence_root=tmp_path / "evidence",
        config_path=config,
    )
    assert second.command == first.command
