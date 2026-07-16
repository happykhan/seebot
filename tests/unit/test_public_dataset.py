import json
from collections import Counter
from pathlib import Path


def test_published_dependency_coverage_matches_project_observations() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))
    projects = dataset["projects"]

    expected = Counter(
        project["dependency_advisories"]["observed"]["coverage_status"] for project in projects
    )
    assert dataset["aggregate"]["dependency_coverage_counts"] == dict(sorted(expected.items()))
    assert set(expected) <= {
        "runtime_scanned",
        "declared_unresolved",
        "installed_inventory_only",
        "development_only",
        "no_supported_input",
        "audit_error",
    }


def test_published_dependency_metrics_only_include_runtime_scans() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))
    projects = {project["id"]: project for project in dataset["projects"]}
    points = dataset["aggregate"]["metric_points"].get("dependency_advisories", [])

    for point in points:
        observed = projects[point["project_id"]]["dependency_advisories"]["observed"]
        assert observed["coverage_status"] == "runtime_scanned"
        assert point["value"] == observed["runtime_advisory_count"]

    runtime_projects = {
        project_id
        for project_id, project in projects.items()
        if project["dependency_advisories"]["observed"]["coverage_status"] == "runtime_scanned"
    }
    assert {point["project_id"] for point in points} == runtime_projects


def test_published_dependency_sources_are_partitioned_by_runtime_role() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))

    for project in dataset["projects"]:
        observed = project["dependency_advisories"]["observed"]
        supported = set(observed.get("supported_sources", []))
        runtime = set(observed.get("runtime_sources", []))
        development = set(observed.get("development_sources", []))
        assert runtime.isdisjoint(development)
        assert runtime | development == supported
        if observed["coverage_status"] != "runtime_scanned":
            assert observed["runtime_advisory_count"] is None


def test_published_dataset_does_not_expose_host_filesystem_paths() -> None:
    root = Path(__file__).parents[2]
    text = (root / "web/public/data/dataset.json").read_text(encoding="utf-8")

    assert "/gpfs3/" not in text
    assert "/well/aanensen/" not in text
    assert "/users/aanensen/" not in text


def test_published_dependency_observations_do_not_expose_absolute_paths() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))

    for project in dataset["projects"]:
        observed = project["dependency_advisories"]["observed"]
        assert not any(Path(source).is_absolute() for source in observed["supported_sources"])
        dependency_results = [row for row in project["results"] if row["domain"] == "dependencies"]
        assert not any(
            '"/' in json.dumps(row.get("observed"), sort_keys=True) for row in dependency_results
        )


def test_published_dataset_keeps_all_normalized_current_results() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))
    normalized = json.loads((root / "results/current/checks.json").read_text(encoding="utf-8"))
    published_counts = {project["id"]: len(project["results"]) for project in dataset["projects"]}
    normalized_counts = Counter(
        row["project_id"] for row in normalized if row.get("run_id") == "current"
    )

    for project_id, expected_count in normalized_counts.items():
        assert published_counts[project_id] == expected_count


def test_published_projects_include_repository_observations() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))
    expected = {
        "REPO-ACTIVITY-001",
        "REPO-DOCUMENTATION-001",
        "REPO-RELEASES-001",
        "REPO-STANDARD-TESTS-001",
        "REPO-VERIFICATION-CI-001",
    }

    for project in dataset["projects"]:
        observed = {row["check_id"] for row in project["results"] if row["domain"] == "repository"}
        assert observed == expected, project["id"]


def test_published_launch_failures_are_never_package_successes() -> None:
    root = Path(__file__).parents[2]
    dataset = json.loads((root / "web/public/data/dataset.json").read_text(encoding="utf-8"))
    launch_failures = []
    for project in dataset["projects"]:
        for contract in project["contracts"]:
            for probe in contract["probes"]:
                stderr = str((probe.get("output") or {}).get("stderr") or "").lower()
                if "command not found" in stderr:
                    launch_failures.append(probe)

    assert all(probe["status"] == "ERROR" for probe in launch_failures)
    assert all(
        probe["observed"].get("audit_error") == "ExecutableLaunchFailure"
        for probe in launch_failures
    )
