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
