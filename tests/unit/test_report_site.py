import json
from pathlib import Path

from seebot.report.site import enrich_repository_rows


def test_enriches_legacy_repository_row_from_retained_tree(tmp_path: Path) -> None:
    package_id = "tool__1__0__linux-64"
    evidence = tmp_path / "evidence" / "old-run" / package_id / "REPO-PRACTICES-001"
    evidence.mkdir(parents=True)
    (evidence / "stdout.json").write_text(
        json.dumps(
            {
                "tree": [
                    {"path": ".github/workflows/test.yml", "type": "blob"},
                    {"path": "tests/test_cli.py", "type": "blob"},
                    {"path": "README.md", "type": "blob"},
                ]
            }
        ),
        encoding="utf-8",
    )
    rows = [
        {
            "package_id": package_id,
            "check_id": "REPO-PRACTICES-001",
            "status": "PASS",
            "observed": {"repository_url": "https://example.test/tool", "observed_commit": "abc"},
            "evidence": {"stdout": "evidence/missing/stdout.json"},
        }
    ]

    enriched = enrich_repository_rows(rows, tmp_path)

    assert enriched[0]["observed"]["test_path_present"] is True
    assert enriched[0]["observed"]["test_file_count"] == 1
    assert enriched[0]["observed"]["ci_workflow_present"] is True
    assert enriched[0]["observed"]["observed_commit"] == "abc"
