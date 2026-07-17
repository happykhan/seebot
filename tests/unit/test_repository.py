import subprocess
from datetime import UTC, datetime
from pathlib import Path

from seebot.analyzers.repository import (
    _active_month_count,
    _dates_at_or_before_cutoff,
    clone_snapshot,
    repository_facts,
)


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


def test_commit_dates_after_canonical_cutoff_are_excluded() -> None:
    dates = [
        datetime(2026, 7, 1, 23, 59, 59, tzinfo=UTC),
        datetime(2026, 7, 2, tzinfo=UTC),
    ]
    assert _dates_at_or_before_cutoff(dates) == dates[:1]


def _committed_repository(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Seebot test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    (path / "source.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.py"], cwd=path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_offline_staged_snapshot_can_be_read_in_place(tmp_path: Path, monkeypatch) -> None:
    staged_root = tmp_path / "snapshots"
    source = staged_root / "pending"
    commit = _committed_repository(source)
    source.rename(staged_root / commit)
    staged = staged_root / commit
    target = tmp_path / "checkout"
    monkeypatch.setenv("SEEBOT_SNAPSHOT_ROOT", str(staged_root))
    monkeypatch.setenv("SEEBOT_STAGED_SNAPSHOT_MODE", "in-place")
    monkeypatch.setenv("SEEBOT_OFFLINE", "1")

    assert clone_snapshot("unused", commit, target) == staged
    assert not target.exists()


def test_staged_snapshot_is_copied_by_default(tmp_path: Path, monkeypatch) -> None:
    staged_root = tmp_path / "snapshots"
    source = staged_root / "pending"
    commit = _committed_repository(source)
    source.rename(staged_root / commit)
    target = tmp_path / "checkout"
    monkeypatch.setenv("SEEBOT_SNAPSHOT_ROOT", str(staged_root))

    assert clone_snapshot("unused", commit, target) == target
    assert (target / "source.py").read_text(encoding="utf-8") == "value = 1\n"
