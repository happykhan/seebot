from datetime import UTC, datetime

from seebot.analyzers.repository import _active_month_count, repository_facts


def test_repository_facts_are_presence_observations() -> None:
    facts = repository_facts(
        [
            ".github/workflows/test.yml",
            ".github/dependabot.yml",
            "CITATION.cff",
            "CHANGELOG.md",
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.rst",
            "Dockerfile",
            "LICENSE",
            "README.md",
            "doc/index.rst",
            "examples/demo.py",
            "pyproject.toml",
            "src/tool.py",
            "tests/data/tiny.fa",
            "tests/test_cli.py",
            "tox.ini",
        ]
    )
    assert facts == {
        "file_count": 16,
        "source_file_count": 3,
        "language_file_counts": {"python": 3},
        "readme_present": True,
        "licence_file_present": True,
        "contribution_guide_present": True,
        "citation_metadata_present": True,
        "code_of_conduct_present": True,
        "issue_templates_present": False,
        "changelog_present": True,
        "ci_workflow_present": True,
        "ci_workflow_count": 1,
        "dependency_automation_present": True,
        "release_automation_present": False,
        "test_path_present": True,
        "test_file_count": 2,
        "test_config_present": True,
        "test_data_present": True,
        "documentation_path_present": True,
        "examples_present": True,
        "dependency_manifest_present": True,
        "lockfile_present": False,
        "container_spec_present": True,
    }


def test_active_months_use_exactly_twelve_calendar_buckets() -> None:
    dates = [
        datetime(2025, 7, 2, tzinfo=UTC),
        datetime(2025, 8, 1, tzinfo=UTC),
        datetime(2026, 7, 1, tzinfo=UTC),
    ]
    assert _active_month_count(dates) == 2
