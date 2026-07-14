import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from seebot.models import Applicability, CheckResult, EvidencePaths, Status, ToolIdentity
from seebot.normalize.results import normalize_run, rebuild_global_results


def test_normalize_writes_json_and_csv(tmp_path: Path) -> None:
    result = CheckResult(
        run_id="pilot",
        package_id="tool__1__0__linux-64",
        check_id="CLI-HELP-001",
        domain="cli",
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
    assert csv_path.read_text().splitlines()[1].startswith("pilot,tool__1__0__linux-64")


def test_rebuild_global_results_combines_runs_deterministically(tmp_path: Path) -> None:
    first = [{"run_id": "run-b", "package_id": "z__1__0__linux-64", "check_id": "B"}]
    second = [{"run_id": "run-a", "package_id": "a__1__0__linux-64", "check_id": "A"}]
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
        row = {
            "run_id": "same-run",
            "package_id": "tool__1__0__linux-64",
            "check_id": "CLI-HELP-001",
            "status": status,
        }
        (target / "checks.json").write_text(json.dumps([row]), encoding="utf-8")

    with pytest.raises(ValueError, match="Conflicting global result key"):
        rebuild_global_results(tmp_path / "results")
