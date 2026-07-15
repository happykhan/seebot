from seebot.reporting import (
    CURRENT_DATE,
    HISTORICAL_DATES,
    REQUIRED_CURRENT_CHECKS,
    _labels,
    _rows_by_check,
)


def test_exemplar_labels_are_boolean_conditions_not_scores() -> None:
    rows = [
        {
            "check_id": check_id,
            "snapshot_date": CURRENT_DATE,
            "status": "OBSERVED",
            "result_kind": "MEASUREMENT",
            "domain": "repository",
            "observed": {},
        }
        for check_id in REQUIRED_CURRENT_CHECKS
    ]
    by_id = {row["check_id"]: row for row in rows}
    by_id["REPO-ACTIVITY-001"]["observed"] = {"archived": False}
    by_id["REPO-DOCUMENTATION-001"]["observed"] = {
        "readme_present": True,
        "installation_instructions_present": True,
        "usage_example_present": True,
        "licence_file_present": True,
        "citation_instructions_present": True,
    }
    by_id["REPO-STANDARD-TESTS-001"]["observed"] = {"recognised_test_count": 1}
    by_id["REPO-VERIFICATION-CI-001"]["observed"] = {"verification_workflow_present": True}
    for check_id in [value for value in REQUIRED_CURRENT_CHECKS if value.startswith("CLI-")]:
        by_id[check_id]["status"] = "PASS"
        by_id[check_id]["result_kind"] = "CONTRACT"
        by_id[check_id]["domain"] = "usage"
    rows.extend(
        {
            "check_id": "SRC-INVENTORY-001",
            "snapshot_date": snapshot_date,
            "status": "OBSERVED",
            "result_kind": "MEASUREMENT",
            "domain": "source",
            "observed": {},
        }
        for snapshot_date in HISTORICAL_DATES
    )

    labels = _labels(rows, _rows_by_check(rows))

    assert labels == {
        "usage_exemplar": True,
        "repository_practice_exemplar": True,
        "complete_assessment": True,
        "practice_exemplar": True,
    }
    assert not any("score" in key for key in labels)
