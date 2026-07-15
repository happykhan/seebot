"""Repository-practice observations at a recorded upstream commit."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from seebot.evidence import (
    audit_code_identity,
    environment_id,
    evidence_path,
    sha256_file,
)
from seebot.models import CheckResult, EvidencePaths, ResultKind, Status, ToolIdentity


def repository_facts(paths: list[str]) -> dict[str, bool | int | dict[str, int]]:
    lowered = [path.lower() for path in paths]
    names = {Path(path).name.lower() for path in paths}
    workflow_paths = [path for path in lowered if path.startswith(".github/workflows/")]
    test_paths = [
        path
        for path in lowered
        if path.startswith(("test/", "tests/")) or "/tests/" in path or "/test/" in path
    ]
    suffix_groups = {
        "python": {".py", ".pyx"},
        "perl": {".pl", ".pm", ".t"},
        "c": {".c", ".h"},
        "cpp": {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"},
        "rust": {".rs"},
    }
    language_file_counts = {
        language: sum(Path(path).suffix.lower() in suffixes for path in lowered)
        for language, suffixes in suffix_groups.items()
    }
    language_file_counts = {key: value for key, value in language_file_counts.items() if value}
    test_configs = {
        "pytest.ini",
        "tox.ini",
        "noxfile.py",
        "conftest.py",
        "jest.config.js",
        "jest.config.ts",
        "phpunit.xml",
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
        "source_file_count": sum(language_file_counts.values()),
        "language_file_counts": language_file_counts,
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
        "ci_workflow_present": bool(workflow_paths),
        "ci_workflow_count": len(workflow_paths),
        "dependency_automation_present": any(
            path
            in {".github/dependabot.yml", ".github/dependabot.yaml", "renovate.json", ".renovaterc"}
            or Path(path).name.startswith("renovate")
            for path in lowered
        ),
        "release_automation_present": any(
            any(token in Path(path).stem for token in ("release", "publish", "deploy"))
            for path in workflow_paths
        ),
        "test_path_present": bool(test_paths),
        "test_file_count": len(test_paths),
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


def run_repository_observation(
    *,
    repository_url: str,
    commit: str,
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    force: bool = False,
) -> CheckResult:
    check_id = "REPO-PRACTICES-001"
    check_dir = evidence_root / run_id / package_id / check_id
    result_path = check_dir / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    check_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = check_dir / "stdout.json"
    stderr_path = check_dir / "stderr.txt"
    metadata_path = check_dir / "metadata.json"

    parsed = urlparse(repository_url)
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if parsed.hostname != "github.com" or len(parts) != 2:
        raise ValueError(f"Unsupported upstream repository URL: {repository_url}")
    owner, repository = parts
    api_url = f"https://api.github.com/repos/{owner}/{repository}/git/trees/{commit}?recursive=1"
    started = datetime.now(UTC)
    clock = time.monotonic()
    status = Status.ERROR
    observed: dict[str, Any] = {}
    notes: str | None = None
    response_body = ""
    stderr = ""
    try:
        response = httpx.get(api_url, follow_redirects=True, timeout=60)
        response.raise_for_status()
        response_body = response.text
        payload = response.json()
        paths = [item["path"] for item in payload.get("tree", []) if item.get("type") == "blob"]
        observed = repository_facts(paths) | {
            "repository_url": repository_url,
            "observed_commit": commit,
            "tree_truncated": bool(payload.get("truncated", False)),
        }
        status = Status.PASS
    except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
        stderr = f"{type(exc).__name__}: {exc}\n"
        observed = {"repository_url": repository_url, "observed_commit": commit}
        notes = "Repository metadata collection failed; no project judgement was inferred."
    duration = time.monotonic() - clock
    stdout_path.write_text(response_body, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "request_url": api_url,
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "duration_seconds": duration,
                "environment_id": environment_id(),
                "manifest_sha256": manifest_sha256,
                **audit_code_identity(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = CheckResult(
        run_id=run_id,
        package_id=package_id,
        check_id=check_id,
        domain="repository",
        status=status,
        result_kind=ResultKind.MEASUREMENT,
        method="automated_with_manifest",
        expected={"measurement_only": True},
        observed=observed,
        tool=ToolIdentity(name="GitHub REST API", version="2022-11-28"),
        command=None,
        started_at=started,
        duration_seconds=duration,
        environment_id=environment_id(),
        config_sha256=sha256_file(config_path),
        evidence=EvidencePaths(
            stdout=evidence_path(stdout_path, evidence_root),
            stderr=evidence_path(stderr_path, evidence_root),
            metadata=evidence_path(metadata_path, evidence_root),
        ),
        notes=notes,
    )
    result.write(result_path)
    return result
