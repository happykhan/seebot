import json
from pathlib import Path

from seebot.storage import compact_run_evidence, directory_size, prune_owned_directory


def test_owned_cache_pruning_is_scoped(tmp_path: Path) -> None:
    cache = tmp_path / ".seebot-cache"
    cache.mkdir()
    (cache / "data").write_bytes(b"123")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "keep").write_text("keep", encoding="utf-8")
    assert directory_size(cache) == 3
    assert prune_owned_directory(cache) == 3
    assert not cache.exists()
    assert unrelated.exists()


def test_beta_compaction_removes_per_check_tree_after_summary(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    contract = evidence_root / "current" / "tool" / "contract"
    measurement = evidence_root / "current" / "tool" / "measurement"
    contract.mkdir(parents=True)
    measurement.mkdir(parents=True)
    contract_payload = {
        "result_kind": "CONTRACT",
        "evidence": {
            "stdout": "evidence/current/tool/contract/stdout.txt",
            "stderr": "evidence/current/tool/contract/stderr.txt",
            "metadata": "evidence/current/tool/contract/metadata.json",
        },
    }
    measurement_payload = {
        "result_kind": "MEASUREMENT",
        "evidence": {
            "stdout": "evidence/current/tool/measurement/stdout.txt",
            "stderr": "evidence/current/tool/measurement/stderr.txt",
            "metadata": "evidence/current/tool/measurement/metadata.json",
        },
    }
    (contract / "result.json").write_text(json.dumps(contract_payload), encoding="utf-8")
    (measurement / "result.json").write_text(json.dumps(measurement_payload), encoding="utf-8")
    for directory in (contract, measurement):
        (directory / "stdout.txt").write_text("output", encoding="utf-8")
        (directory / "stderr.txt").write_text("diagnostic", encoding="utf-8")
        (directory / "metadata.json").write_text("{}", encoding="utf-8")
    sandbox = measurement / ".fixture-sandbox"
    sandbox.mkdir()
    (sandbox / "input.dat").write_text("fixture", encoding="utf-8")

    files, _ = compact_run_evidence(evidence_root, "current", delete=False)
    assert files == 9
    assert (measurement / "metadata.json").exists()

    compact_run_evidence(evidence_root, "current", delete=True)
    assert not (evidence_root / "current").exists()
