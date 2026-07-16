"""Repository practices and activity at the canonical GitHub snapshot."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from seebot.models import CheckResult, Status, ToolIdentity
from seebot.observations import write_measurement

CUTOFF = datetime(2026, 7, 1, 23, 59, 59, tzinfo=UTC)
ACTIVITY_START = datetime(2025, 7, 2, tzinfo=UTC)
ACTIVE_MONTH_START = datetime(2025, 8, 1, tzinfo=UTC)
RELEASE_START = datetime(2024, 7, 2, tzinfo=UTC)


def github_coordinates(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if parsed.hostname != "github.com" or len(parts) != 2:
        raise ValueError(f"Unsupported GitHub repository URL: {repository_url}")
    return parts[0], parts[1]


def _active_month_count(dates: list[datetime]) -> int:
    """Count activity in the 12 calendar-month buckets ending at the cutoff."""
    return len({date.strftime("%Y-%m") for date in dates if ACTIVE_MONTH_START <= date <= CUTOFF})


def _dates_at_or_before_cutoff(dates: list[datetime]) -> list[datetime]:
    """Apply the canonical cutoff independently of GitHub API date semantics."""
    return [date for date in dates if date <= CUTOFF]


def clone_snapshot(repository_url: str, commit: str, target: Path) -> Path:
    """Create a disposable checkout containing only the audited commit."""
    if target.exists():
        shutil.rmtree(target)
    staged_root = os.environ.get("SEEBOT_SNAPSHOT_ROOT")
    if staged_root:
        staged = Path(staged_root) / commit
        if not staged.is_dir():
            raise FileNotFoundError(f"Prepared snapshot does not exist: {staged}")
        shutil.copytree(staged, target, symlinks=True)
        observed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=target, capture_output=True, text=True, check=True
        ).stdout.strip()
        if observed != commit:
            raise RuntimeError(f"Expected staged snapshot {commit}, copied {observed}")
        return target
    target.mkdir(parents=True)
    commands = (
        ["git", "init", "--quiet"],
        ["git", "remote", "add", "origin", repository_url],
        ["git", "fetch", "--quiet", "--depth", "1", "origin", commit],
        ["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"],
    )
    for command in commands:
        completed = subprocess.run(command, cwd=target, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Snapshot checkout failed: {completed.stderr.strip()}")
    observed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=target, capture_output=True, text=True, check=True
    ).stdout.strip()
    if observed != commit:
        raise RuntimeError(f"Expected snapshot {commit}, checked out {observed}")
    return target


def repository_facts(paths: list[str]) -> dict[str, bool | int | dict[str, int]]:
    """Path-only facts retained for deterministic inventory tests and reporting."""
    lowered = [path.lower() for path in paths]
    names = {Path(path).name.lower() for path in paths}
    workflows = [path for path in lowered if path.startswith(".github/workflows/")]
    tests = [
        path
        for path in lowered
        if path.startswith(("test/", "tests/", "t/", "src/test/"))
        or "/tests/" in path
        or "/test/" in path
    ]
    suffixes = {
        "python": {".py", ".pyx"},
        "perl": {".pl", ".pm", ".t"},
        "c": {".c", ".h"},
        "cpp": {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"},
        "rust": {".rs"},
        "java": {".java"},
    }
    language_counts = {
        language: sum(Path(path).suffix.lower() in endings for path in lowered)
        for language, endings in suffixes.items()
    }
    language_counts = {key: value for key, value in language_counts.items() if value}
    test_configs = {
        "pytest.ini",
        "tox.ini",
        "noxfile.py",
        "conftest.py",
        "cargo.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "ctesttestfile.cmake",
    }
    dependency_manifests = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "environment.yml",
        "environment.yaml",
        "cargo.toml",
        "cpanfile",
        "makefile.pl",
        "package.json",
        "cmakelists.txt",
        "configure.ac",
        "meson.build",
        "pom.xml",
        "build.gradle",
    }
    lockfiles = {
        "uv.lock",
        "poetry.lock",
        "pipfile.lock",
        "cargo.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "conda-lock.yml",
        "conda-lock.yaml",
    }
    return {
        "file_count": len(paths),
        "source_file_count": sum(language_counts.values()),
        "language_file_counts": language_counts,
        "readme_present": any(name.startswith("readme") for name in names),
        "licence_file_present": bool(
            names
            & {
                "license",
                "license.md",
                "license.rst",
                "license.txt",
                "licence",
                "licence.md",
                "licence.txt",
                "copying",
            }
        ),
        "contribution_guide_present": any(name.startswith("contributing") for name in names),
        "citation_metadata_present": "citation.cff" in names,
        "code_of_conduct_present": any(name.startswith("code_of_conduct") for name in names),
        "issue_templates_present": any(
            path.startswith(".github/issue_template/") for path in lowered
        ),
        "changelog_present": any(
            name.startswith(("changelog", "changes", "history")) for name in names
        ),
        "ci_workflow_present": bool(workflows),
        "ci_workflow_count": len(workflows),
        "dependency_automation_present": any(
            path in {".github/dependabot.yml", ".github/dependabot.yaml", "renovate.json"}
            or Path(path).name.startswith("renovate")
            for path in lowered
        ),
        "release_automation_present": any(
            any(token in Path(path).stem for token in ("release", "publish", "deploy"))
            for path in workflows
        ),
        "test_path_present": bool(tests),
        "test_file_count": len(tests),
        "test_config_present": bool(names & test_configs),
        "test_data_present": any(
            path.startswith(("test/data/", "tests/data/", "test/fixtures/", "tests/fixtures/"))
            or "/testdata/" in path
            or "/test_data/" in path
            for path in lowered
        ),
        "documentation_path_present": any(
            path.startswith(("doc/", "docs/", "documentation/")) for path in lowered
        ),
        "examples_present": any(
            path.startswith(("example/", "examples/", "tutorial/", "tutorials/"))
            for path in lowered
        ),
        "dependency_manifest_present": bool(names & dependency_manifests),
        "lockfile_present": bool(names & lockfiles),
        "container_spec_present": any(
            name.startswith("dockerfile") or path.startswith(".devcontainer/")
            for path, name in zip(lowered, (Path(path).name for path in lowered), strict=True)
        ),
    }


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def repository_practices(root: Path) -> dict[str, Any]:
    paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    facts = repository_facts(paths)
    readme_paths = [
        path for path in root.iterdir() if path.is_file() and path.name.lower().startswith("readme")
    ]
    readme = "\n".join(_text(path) for path in readme_paths)
    lowered_readme = readme.lower()
    recognised: list[str] = []
    frameworks: set[str] = set()
    for relative in paths:
        lower = relative.lower()
        name = Path(relative).name.lower()
        content = _text(root / relative) if (root / relative).stat().st_size < 2_000_000 else ""
        if (
            re.search(r"(^|/)(test_[^/]+|[^/]+_test)\.py$", lower)
            or re.search(r"(^|/)t/[^/]+\.t$", lower)
            or lower.startswith("src/test/java/")
            or re.search(r"(^|/)tests?/.*\.(?:c|cc|cpp|cxx|rs)$", lower)
            or "#[test]" in content.replace(" ", "")
        ):
            recognised.append(relative)
        for framework, pattern in {
            "pytest": r"pytest|@pytest\.",
            "unittest": r"unittest|testcase",
            "prove/Test::More": r"test::more|\bprove\b",
            "CTest": r"enable_testing|add_test|\bctest\b",
            "GoogleTest": r"gtest|google\s*test",
            "Catch2": r"catch2|catch_test_case|test_case\s*\(",
            "Rust test": r"#\s*\[\s*test\s*\]|cargo\s+test",
            "JUnit": r"org\.junit|junit-jupiter|@test",
        }.items():
            if re.search(pattern, content, re.IGNORECASE):
                frameworks.add(framework)
        if name in {"pytest.ini", "tox.ini", "noxfile.py"}:
            frameworks.add("pytest")
    workflows = [path for path in paths if path.lower().startswith(".github/workflows/")]
    verification: list[str] = []
    workflow_types: set[str] = set()
    verification_patterns = {
        "test": (
            r"pytest|unittest|\bprove\b|cargo\s+test|\bctest\b|mvn\s+test|"
            r"gradle\w*\s+test|make\s+(?:check|test)"
        ),
        "lint": r"ruff|pylint|perlcritic|cppcheck|clang-tidy|cargo\s+clippy|checkstyle",
        "build/check": (
            r"cargo\s+(?:build|check)|cmake\s|make\b|mvn\s+(?:package|verify)|"
            r"gradle\w*\s+build"
        ),
    }
    for relative in workflows:
        content = _text(root / relative)
        matched = [
            kind
            for kind, pattern in verification_patterns.items()
            if re.search(pattern, content, re.IGNORECASE)
        ]
        if matched:
            verification.append(relative)
            workflow_types.update(matched)
    citation = bool(facts["citation_metadata_present"]) or bool(
        re.search(r"\bcit(?:e|ation)\b|bibtex|doi\.org/", lowered_readme)
    )
    installation = bool(
        re.search(
            r"\binstall(?:ation|ing)?\b|pip\s+install|conda\s+install|cargo\s+install",
            lowered_readme,
        )
    )
    usage = bool(re.search(r"\busage\b|\bexamples?\b|```(?:bash|shell|console|sh)", lowered_readme))
    return facts | {
        "installation_instructions_present": installation,
        "usage_example_present": usage,
        "citation_instructions_present": citation,
        "recognised_test_files": recognised,
        "test_frameworks": sorted(frameworks),
        "verification_workflows": verification,
        "verification_workflow_types": sorted(workflow_types),
    }


def _github_headers() -> dict[str, str]:
    executable = shutil.which("gh")
    token = (
        subprocess.run(
            [executable, "auth", "token"], capture_output=True, text=True, check=False
        ).stdout.strip()
        if executable
        else ""
    )
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _pages(client: httpx.Client, url: str, *, maximum_pages: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, maximum_pages + 1):
        response = client.get(url, params={"per_page": 100, "page": page})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("GitHub list endpoint returned a non-list payload")
        rows.extend(payload)
        if len(payload) < 100:
            break
    return rows


def _unknown_github_activity(error: str) -> dict[str, Any]:
    return {
        "github_api_available": False,
        "github_api_error": error,
        "archived": None,
        "days_since_last_non_bot_commit": None,
        "commits_last_12_months": None,
        "active_months_last_12_months": None,
        "days_since_latest_release": None,
        "releases_last_24_months": None,
        "latest_release_tag": None,
    }


def github_activity(repository_url: str) -> dict[str, Any]:
    owner, repository = github_coordinates(repository_url)
    base = f"https://api.github.com/repos/{owner}/{repository}"
    try:
        with httpx.Client(headers=_github_headers(), timeout=60, follow_redirects=True) as client:
            repository_response = client.get(base)
            repository_response.raise_for_status()
            repository_payload = repository_response.json()
            activity_commits = _pages(
                client,
                (f"{base}/commits?since={ACTIVITY_START.isoformat()}&until={CUTOFF.isoformat()}"),
                maximum_pages=100,
            )
            recent_commits = _pages(
                client, f"{base}/commits?until={CUTOFF.isoformat()}", maximum_pages=5
            )
            releases = _pages(client, f"{base}/releases", maximum_pages=5)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {403, 429}:
            return _unknown_github_activity(f"HTTP {exc.response.status_code}: {exc.response.text}")
        raise
    except httpx.RequestError as exc:
        return _unknown_github_activity(f"{type(exc).__name__}: {exc}")
    payload_root = os.environ.get("SEEBOT_GITHUB_PAYLOAD_ROOT")
    if payload_root:
        target = Path(payload_root) / f"{owner}--{repository}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "repository": repository_payload,
                    "activity_commits": activity_commits,
                    "recent_commits": recent_commits,
                    "releases": releases,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    non_bot_commits: list[dict[str, Any]] = []
    seen_commits: set[str] = set()
    for row in [*activity_commits, *recent_commits]:
        sha = str(row.get("sha") or "")
        if sha and sha in seen_commits:
            continue
        seen_commits.add(sha)
        author = row.get("author") or {}
        commit_author = (row.get("commit") or {}).get("author") or {}
        identity = f"{author.get('login', '')} {commit_author.get('name', '')}".lower()
        if any(
            token in identity for token in ("[bot]", "dependabot", "renovate", "github-actions")
        ):
            continue
        non_bot_commits.append(row)
    all_dates = [
        datetime.fromisoformat(row["commit"]["author"]["date"].replace("Z", "+00:00"))
        for row in non_bot_commits
        if row.get("commit", {}).get("author", {}).get("date")
    ]
    cutoff_dates = _dates_at_or_before_cutoff(all_dates)
    dates = [date for date in cutoff_dates if date >= ACTIVITY_START]
    all_release_dates = [
        datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
        for row in releases
        if row.get("published_at")
        and datetime.fromisoformat(row["published_at"].replace("Z", "+00:00")) <= CUTOFF
    ]
    release_dates = [date for date in all_release_dates if date >= RELEASE_START]
    latest_commit = max(cutoff_dates, default=None)
    latest_release = max(all_release_dates, default=None)
    return {
        "github_api_available": True,
        "github_api_error": None,
        "archived": bool(repository_payload.get("archived")),
        "days_since_last_non_bot_commit": (CUTOFF - latest_commit).days if latest_commit else None,
        "commits_last_12_months": len(dates),
        "active_months_last_12_months": _active_month_count(dates),
        "days_since_latest_release": (CUTOFF - latest_release).days if latest_release else None,
        "releases_last_24_months": len(release_dates),
        "latest_release_tag": next(
            (
                row.get("tag_name")
                for row in releases
                if row.get("published_at")
                and datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
                == latest_release
            ),
            None,
        ),
    }


def run_repository_observations(
    *,
    manifest: dict[str, Any],
    checkout: Path,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    force: bool = False,
) -> list[CheckResult]:
    project_id = manifest["project"]["id"]
    repository_url = manifest["repository"]["url"]
    commit = manifest["repository"]["snapshot_commit"]
    snapshot_date = manifest["repository"]["snapshot_date"]
    if not repository_url or not commit:
        raise ValueError(f"{project_id} has no resolved repository snapshot")
    owner, repository = github_coordinates(repository_url)
    repository_id = f"{owner}/{repository}"
    practices = repository_practices(checkout)
    activity = github_activity(repository_url)
    activity_status = (
        Status.OBSERVED if activity.get("github_api_available", True) else Status.UNTESTABLE
    )
    activity_notes = (
        None
        if activity_status is Status.OBSERVED
        else (
            "GitHub API activity endpoints were unavailable; "
            "local repository observations remain recorded."
        )
    )
    tool = ToolIdentity(name="Seebot repository observer", version="2")
    documentation = {
        key: practices[key]
        for key in (
            "readme_present",
            "licence_file_present",
            "citation_instructions_present",
            "installation_instructions_present",
            "usage_example_present",
            "documentation_path_present",
            "changelog_present",
            "contribution_guide_present",
            "issue_templates_present",
            "code_of_conduct_present",
            "dependency_automation_present",
            "release_automation_present",
        )
    }
    return [
        write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="REPO-ACTIVITY-001",
            probe_id="repository:activity",
            domain="repository",
            status=activity_status,
            observed=activity,
            evidence_root=evidence_root,
            config_path=config_path,
            snapshot_date=snapshot_date,
            snapshot_commit=commit,
            repository_id=repository_id,
            tool=tool,
            notes=activity_notes,
            force=force,
        ),
        write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="REPO-DOCUMENTATION-001",
            probe_id="repository:documentation",
            domain="repository",
            status=Status.OBSERVED,
            observed=documentation,
            evidence_root=evidence_root,
            config_path=config_path,
            snapshot_date=snapshot_date,
            snapshot_commit=commit,
            repository_id=repository_id,
            tool=tool,
            force=force,
        ),
        write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="REPO-STANDARD-TESTS-001",
            probe_id="repository:standard-tests",
            domain="repository",
            status=Status.OBSERVED,
            observed={
                "frameworks": practices["test_frameworks"],
                "recognised_test_files": practices["recognised_test_files"],
                "recognised_test_count": len(practices["recognised_test_files"]),
            },
            evidence_root=evidence_root,
            config_path=config_path,
            snapshot_date=snapshot_date,
            snapshot_commit=commit,
            repository_id=repository_id,
            tool=tool,
            notes="Upstream tests were detected but never executed.",
            force=force,
        ),
        write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="REPO-VERIFICATION-CI-001",
            probe_id="repository:verification-ci",
            domain="repository",
            status=Status.OBSERVED,
            observed={
                "verification_workflow_present": bool(practices["verification_workflows"]),
                "workflow_paths": practices["verification_workflows"],
                "workflow_types": practices["verification_workflow_types"],
                "latest_state": "NOT_ASSESSED",
            },
            evidence_root=evidence_root,
            config_path=config_path,
            snapshot_date=snapshot_date,
            snapshot_commit=commit,
            repository_id=repository_id,
            tool=tool,
            force=force,
        ),
        write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="REPO-RELEASES-001",
            probe_id="repository:releases",
            domain="repository",
            status=activity_status,
            observed={key: value for key, value in activity.items() if "release" in key},
            evidence_root=evidence_root,
            config_path=config_path,
            snapshot_date=snapshot_date,
            snapshot_commit=commit,
            repository_id=repository_id,
            tool=tool,
            notes=activity_notes,
            force=force,
        ),
    ]
