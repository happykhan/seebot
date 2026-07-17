from seebot.reporting import (
    CURRENT_DATE,
    HISTORICAL_DATES,
    REQUIRED_CURRENT_CHECKS,
    _dependency_summary,
    _evidence_excerpt,
    _labels,
    _rows_by_check,
    _source_snapshots,
)


def test_exemplar_labels_are_boolean_conditions_not_scores() -> None:
    assert "CLI-SEMANTICALLY-EMPTY-INPUT-001" in REQUIRED_CURRENT_CHECKS
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


def test_public_output_excerpt_is_bounded_and_cannot_escape_repository(tmp_path) -> None:
    evidence = tmp_path / "evidence" / "stderr.txt"
    evidence.parent.mkdir()
    evidence.write_text("useful diagnostic\n" + "x" * 50, encoding="utf-8")

    excerpt = _evidence_excerpt(tmp_path, {"stderr": "evidence/stderr.txt"}, "stderr", 25)
    assert excerpt == "useful diagnostic\nxxxxxxx\n…"
    assert _evidence_excerpt(tmp_path, {"stderr": "../secret.txt"}, "stderr") is None


def test_documentation_coverage_is_a_valid_percentage_in_public_snapshot() -> None:
    rows = [
        {
            "check_id": "SRC-DOCUMENTATION-001",
            "snapshot_date": CURRENT_DATE,
            "snapshot_commit": "abc",
            "domain": "source",
            "source_component_id": "perl:main",
            "status": "OBSERVED",
            "observed": {
                "function_count": 3,
                "documented_functions": 14,
                "coverage_percent": 466.67,
            },
        }
    ]

    documentation = _source_snapshots(rows)[0]["metrics"]["documentation"]

    assert documentation["coverage_percent"] == 100
    assert documentation["documented_functions"] == 3


def test_dependency_summary_separates_runtime_and_development_inputs() -> None:
    summary = _dependency_summary(
        [
            {
                "status": "OBSERVED",
                "observed": {
                    "supported_sources": [
                        "Cargo.lock",
                        "docs/requirements.txt",
                        ".github/workflows/requirements.txt",
                    ],
                    "advisories": [
                        {"advisory_id": "RUSTSEC-1", "source": "Cargo.lock"},
                        {"advisory_id": "PYSEC-1", "source": "docs/requirements.txt"},
                        {
                            "advisory_id": "PYSEC-2",
                            "source": ".github/workflows/requirements.txt",
                        },
                    ],
                },
            },
        ],
        "rust",
    )
    assert summary["coverage_status"] == "runtime_scanned"
    assert summary["runtime_sources"] == ["Cargo.lock"]
    assert summary["development_sources"] == [
        ".github/workflows/requirements.txt",
        "docs/requirements.txt",
    ]
    assert summary["runtime_advisory_count"] == 1


def test_dependency_summary_does_not_publish_absolute_checkout_paths() -> None:
    checkout_source = "/private/audit/work/checkouts/cooler/2026-07-01/docs/requirements.txt"
    summary = _dependency_summary(
        [
            {
                "status": "OBSERVED",
                "observed": {
                    "supported_sources": [checkout_source],
                    "advisories": [{"advisory_id": "PYSEC-1", "source": checkout_source}],
                },
            }
        ],
        "python",
    )

    assert summary["supported_sources"] == ["docs/requirements.txt"]
    assert summary["development_sources"] == ["docs/requirements.txt"]
    assert summary["advisories"][0]["source"] == "docs/requirements.txt"


def test_dependency_summary_does_not_report_zero_for_development_only_inputs() -> None:
    summary = _dependency_summary(
        [
            {
                "status": "OBSERVED",
                "observed": {
                    "supported_sources": ["benches/requirements.txt"],
                    "advisories": [],
                },
            }
        ],
        "python",
    )
    assert summary["coverage_status"] == "development_only"
    assert summary["runtime_advisory_count"] is None


def test_dependency_summary_merges_aliases_for_one_vulnerability() -> None:
    summary = _dependency_summary(
        [
            {
                "status": "OBSERVED",
                "observed": {
                    "supported_sources": ["installed-environment:PyPI"],
                    "advisories": [
                        {
                            "advisory_id": "GHSA-example",
                            "aliases": ["CVE-2026-1", "PYSEC-2026-1"],
                            "ecosystem": "PyPI",
                            "dependency": "example",
                            "resolved_version": "1.0",
                            "source": "installed-environment:PyPI",
                            "native_severity": ["CVSS_V3:first"],
                            "fixed_versions": ["1.1"],
                        },
                        {
                            "advisory_id": "PYSEC-2026-1",
                            "aliases": ["CVE-2026-1", "GHSA-example"],
                            "ecosystem": "PyPI",
                            "dependency": "example",
                            "resolved_version": "1.0",
                            "source": "installed-environment:PyPI",
                            "native_severity": ["CVSS_V4:second"],
                            "fixed_versions": ["1.2"],
                        },
                    ],
                },
            }
        ],
        "python",
    )

    assert summary["runtime_advisory_count"] == 1
    assert summary["advisory_count"] == 1
    assert summary["advisories"][0]["advisory_id"] == "GHSA-example"
    assert summary["advisories"][0]["aliases"] == ["CVE-2026-1", "PYSEC-2026-1"]
    assert summary["advisories"][0]["fixed_versions"] == ["1.1", "1.2"]
    assert summary["advisories"][0]["native_severity"] == ["CVSS_V3:first", "CVSS_V4:second"]
    assert summary["advisories"][0]["native_severity"] == [
        "CVSS_V3:first",
        "CVSS_V4:second",
    ]


def test_dependency_summary_combines_repository_and_installed_evidence() -> None:
    summary = _dependency_summary(
        [
            {
                "probe_id": "dependencies:osv-scanner",
                "status": "NOT_APPLICABLE",
                "observed": {
                    "declared_dependencies": [
                        {
                            "ecosystem": "PyPI",
                            "name": "archspec",
                            "role": "runtime",
                            "source": "pyproject.toml",
                            "raw": "archspec~=0.2",
                        }
                    ],
                    "supported_sources": [],
                    "advisories": [],
                },
            },
            {
                "probe_id": "dependencies:installed-environment",
                "status": "OBSERVED",
                "observed": {
                    "supported_sources": ["installed-environment:PyPI"],
                    "conda_packages": [{"name": "archspec", "version": "0.2.5"}],
                    "ecosystem_packages": [
                        {"ecosystem": "PyPI", "name": "archspec", "version": "0.2.5"}
                    ],
                    "advisories": [],
                },
            },
        ],
        "python",
    )

    assert summary["coverage_status"] == "runtime_scanned"
    assert summary["runtime_sources"] == ["installed-environment:PyPI"]
    assert summary["runtime_advisory_count"] == 0
    assert summary["conda_package_count"] == 1
    assert summary["ecosystem_package_count"] == 1


def test_dependency_summary_keeps_conda_only_inventory_distinct_from_a_scan() -> None:
    summary = _dependency_summary(
        [
            {
                "probe_id": "dependencies:installed-environment",
                "status": "NOT_APPLICABLE",
                "observed": {
                    "supported_sources": [],
                    "conda_packages": [{"name": "native-tool", "version": "1.0"}],
                    "ecosystem_packages": [],
                    "advisories": [],
                },
            }
        ],
        "c",
    )

    assert summary["coverage_status"] == "installed_inventory_only"
    assert summary["runtime_advisory_count"] is None
