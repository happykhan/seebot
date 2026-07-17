import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from seebot.models import Applicability, CheckResult, EvidencePaths, Status, ToolIdentity
from seebot.normalize.results import normalize_run, rebuild_global_results


def result_row(run_id: str, project_id: str, check_id: str, status: Status = Status.PASS):
    return CheckResult(
        run_id=run_id,
        project_id=project_id,
        snapshot_date="2026-07-01",
        check_id=check_id,
        probe_id=f"probe:{check_id}",
        domain="usage",
        status=status,
        expected={},
        observed={},
        tool=ToolIdentity(name="seebot", version="2"),
        command=["tool"],
        started_at=datetime.now(UTC),
        duration_seconds=0.1,
        environment_id="sha256:test",
        config_sha256="0" * 64,
        evidence=EvidencePaths(stdout="stdout.txt", stderr="stderr.txt", metadata="metadata.json"),
    ).model_dump(mode="json")


def test_normalize_writes_json_and_csv(tmp_path: Path) -> None:
    result = CheckResult(
        run_id="pilot",
        project_id="tool",
        snapshot_date="2026-07-01",
        check_id="CLI-HELP-001",
        probe_id="cli-help-001:tool-help",
        domain="usage",
        status=Status.PASS,
        applicability=Applicability.APPLICABLE,
        expected={"exit_codes": [0]},
        observed={"exit_code": 0},
        tool=ToolIdentity(name="seebot", version="0.1.0"),
        command=["tool", "--help"],
        started_at=datetime.now(UTC),
        duration_seconds=0.1,
        environment_id="sha256:test",
        config_sha256="0" * 64,
        evidence=EvidencePaths(stdout="stdout.txt", stderr="stderr.txt", metadata="metadata.json"),
    )
    result.write(tmp_path / "evidence" / "pilot" / "tool" / "check" / "result.json")
    json_path, csv_path = normalize_run(tmp_path / "evidence", tmp_path / "results", "pilot")
    assert json_path.exists()
    assert csv_path.read_text().splitlines()[1].startswith("pilot,tool,")


def test_rebuild_global_results_combines_runs_deterministically(tmp_path: Path) -> None:
    first = [result_row("run-b", "z", "B")]
    second = [result_row("run-a", "a", "A")]
    for run_id, rows in (("run-b", first), ("run-a", second)):
        target = tmp_path / "results" / run_id
        target.mkdir(parents=True)
        (target / "checks.json").write_text(json.dumps(rows), encoding="utf-8")

    json_path, csv_path = rebuild_global_results(tmp_path / "results")

    rows = json.loads(json_path.read_text(encoding="utf-8"))
    assert [row["run_id"] for row in rows] == ["run-a", "run-b"]
    assert len(csv_path.read_text(encoding="utf-8").splitlines()) == 3


def test_rebuild_global_results_rejects_conflicting_natural_key(tmp_path: Path) -> None:
    for directory, status in (("one", "PASS"), ("two", "FAIL")):
        target = tmp_path / "results" / directory
        target.mkdir(parents=True)
        row = result_row("same-run", "tool", "CLI-HELP-001", Status(status))
        (target / "checks.json").write_text(json.dumps([row]), encoding="utf-8")

    with pytest.raises(ValueError, match="Conflicting global result key"):
        rebuild_global_results(tmp_path / "results")


def test_normalize_overwrites_existing_checks_from_evidence(tmp_path: Path) -> None:
    target = tmp_path / "results" / "pilot"
    target.mkdir(parents=True)
    existing = [result_row("pilot", "tool", "OLD")]
    (target / "checks.json").write_text(json.dumps(existing), encoding="utf-8")
    evidence = tmp_path / "evidence" / "pilot" / "tool" / "NEW"
    evidence.mkdir(parents=True)
    (evidence / "result.json").write_text(
        json.dumps(result_row("pilot", "tool", "NEW")), encoding="utf-8"
    )

    json_path, _ = normalize_run(tmp_path / "evidence", tmp_path / "results", "pilot")

    assert [row["check_id"] for row in json.loads(json_path.read_text())] == ["NEW"]


def test_normalize_ignores_archived_results_beneath_run_root(tmp_path: Path) -> None:
    current = tmp_path / "evidence" / "pilot" / "tool" / "NEW"
    current.mkdir(parents=True)
    (current / "result.json").write_text(
        json.dumps(result_row("pilot", "tool", "NEW")), encoding="utf-8"
    )
    archived = tmp_path / "evidence" / "pilot" / "_stale-contracts" / "tool" / "OLD"
    archived.mkdir(parents=True)
    (archived / "result.json").write_text(
        json.dumps(result_row("pilot", "tool", "OLD")), encoding="utf-8"
    )

    json_path, _ = normalize_run(tmp_path / "evidence", tmp_path / "results", "pilot")

    assert [row["check_id"] for row in json.loads(json_path.read_text())] == ["NEW"]
