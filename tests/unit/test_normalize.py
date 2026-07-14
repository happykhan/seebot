from datetime import UTC, datetime
from pathlib import Path

from bioconda_audit.models import Applicability, CheckResult, EvidencePaths, Status, ToolIdentity
from bioconda_audit.normalize.results import normalize_run


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
        tool=ToolIdentity(name="bcqa", version="0.1.0"),
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
