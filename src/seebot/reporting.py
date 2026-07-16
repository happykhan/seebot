"""Build the public observation dataset without inventing scores or rankings."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from seebot.manifests import load_yaml

CURRENT_DATE = "2026-07-01"
HISTORICAL_DATES = [f"{year}-07-01" for year in range(2021, 2026)]
ROBUSTNESS_IDS = {
    "CLI-MISSING-INPUT-001": "Missing input",
    "CLI-EMPTY-INPUT-001": "Zero-byte input",
    "CLI-SEMANTICALLY-EMPTY-INPUT-001": "Valid input with no records",
    "CLI-MALFORMED-INPUT-001": "Malformed expected format",
    "CLI-WRONG-FORMAT-001": "Wrong biological format",
    "CLI-INVALID-OPTION-001": "Unrecognized option",
    "CLI-INVALID-VALUE-001": "Invalid parameter value",
    "CLI-UNWRITABLE-OUTPUT-001": "Unwritable output",
}
REQUIRED_CURRENT_CHECKS = {
    "REPO-ACTIVITY-001",
    "REPO-RELEASES-001",
    "REPO-DOCUMENTATION-001",
    "REPO-STANDARD-TESTS-001",
    "REPO-VERIFICATION-CI-001",
    "SRC-INVENTORY-001",
    "SRC-FILE-LENGTH-001",
    "SRC-FUNCTION-STRUCTURE-001",
    "SRC-COMPLEXITY-001",
    "SRC-DUPLICATION-001",
    "SRC-DOCUMENTATION-001",
    "SRC-NATIVE-LINT-001",
    "SRC-NATIVE-SECURITY-001",
    "SRC-DEAD-CODE-001",
    "DEP-ADVISORY-001",
    "CLI-HELP-001",
    "CLI-VERSION-001",
    "CLI-NOARGS-001",
    "CLI-VALID-RUN-001",
    "CLI-STREAMS-001",
    *ROBUSTNESS_IDS,
}
REJECT_COVERAGE = {"UNTESTABLE", "ERROR", "NOT_RUN"}
DEVELOPMENT_PATH_PARTS = {
    ".circleci",
    ".github",
    "bench",
    "benches",
    "benchmark",
    "benchmarks",
    "ci",
    "dev",
    "doc",
    "docs",
    "example",
    "examples",
    "test",
    "tests",
}
STATUS_TEXT = {
    "PASS": "Handled gracefully",
    "FAIL": "Did not handle gracefully",
    "OBSERVED": "Observed",
    "NOT_OBSERVED": "Not observed",
    "NOT_APPLICABLE": "Not applicable",
    "UNTESTABLE": "Could not assess",
    "ERROR": "Audit error",
    "NOT_RUN": "Not run",
    "NOT_EXISTING": "Project not yet present",
}


def _rows_by_check(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["check_id"])].append(row)
    return dict(grouped)


def _current_row(grouped: dict[str, list[dict[str, Any]]], check_id: str) -> dict[str, Any]:
    candidates = [row for row in grouped.get(check_id, []) if row["snapshot_date"] == CURRENT_DATE]
    return candidates[0] if candidates else {}


def _observed(grouped: dict[str, list[dict[str, Any]]], check_id: str) -> dict[str, Any]:
    row = _current_row(grouped, check_id)
    observed = row.get("observed")
    return observed if isinstance(observed, dict) else {}


def _evidence_excerpt(
    repository_root: Path, evidence: dict[str, Any], stream: str, limit: int = 1200
) -> str | None:
    raw_path = evidence.get(stream)
    if not isinstance(raw_path, str):
        return None
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved = repository_root / path
    if not resolved.is_file():
        return None
    text = resolved.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    return text if len(text) <= limit else f"{text[:limit].rstrip()}\n…"


def _contract_summary(rows: list[dict[str, Any]], repository_root: Path) -> list[dict[str, Any]]:
    grouped = _rows_by_check(
        [
            row
            for row in rows
            if row.get("result_kind") == "CONTRACT" and row.get("snapshot_date") == CURRENT_DATE
        ]
    )
    output: list[dict[str, Any]] = []
    for check_id in sorted(grouped):
        probes = sorted(grouped[check_id], key=lambda row: str(row.get("probe_id")))
        statuses = [str(row["status"]) for row in probes]
        if "ERROR" in statuses:
            status = "ERROR"
        elif "UNTESTABLE" in statuses:
            status = "UNTESTABLE"
        elif "FAIL" in statuses:
            status = "FAIL"
        elif all(value == "NOT_APPLICABLE" for value in statuses):
            status = "NOT_APPLICABLE"
        else:
            status = "PASS"
        output.append(
            {
                "check_id": check_id,
                "status": status,
                "label": ROBUSTNESS_IDS.get(check_id, check_id),
                "domain": probes[0]["domain"],
                "probes": [
                    {
                        "probe_id": row["probe_id"],
                        "status": row["status"],
                        "status_text": STATUS_TEXT.get(str(row["status"]), str(row["status"])),
                        "command": row.get("command"),
                        "observed": row.get("observed", {}),
                        "notes": row.get("notes"),
                        "evidence": row.get("evidence", {}),
                        "output": {
                            "stdout": _evidence_excerpt(
                                repository_root, row.get("evidence", {}), "stdout"
                            ),
                            "stderr": _evidence_excerpt(
                                repository_root, row.get("evidence", {}), "stderr"
                            ),
                        },
                    }
                    for row in probes
                ],
            }
        )
    return output


def _source_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshots: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("domain") != "source":
            continue
        component = str(row.get("source_component_id") or "unknown")
        language = component.split(":", 1)[0]
        key = (str(row["snapshot_date"]), language)
        snapshot = snapshots.setdefault(
            key,
            {
                "snapshot_date": row["snapshot_date"],
                "snapshot_commit": row.get("snapshot_commit"),
                "language": language,
                "status": row["status"],
                "metrics": {},
                "native_findings": [],
            },
        )
        status = str(row["status"])
        if status in REJECT_COVERAGE or status == "NOT_EXISTING":
            snapshot["status"] = status
        check_id = str(row["check_id"])
        raw_observed = row.get("observed")
        observed: dict[str, Any] = raw_observed if isinstance(raw_observed, dict) else {}
        if check_id == "SRC-INVENTORY-001":
            snapshot["metrics"]["inventory"] = observed
        elif check_id == "SRC-FILE-LENGTH-001":
            snapshot["metrics"]["files"] = observed
        elif check_id == "SRC-FUNCTION-STRUCTURE-001":
            snapshot["metrics"]["functions"] = observed
        elif check_id == "SRC-COMPLEXITY-001":
            snapshot["metrics"]["complexity"] = observed
        elif check_id == "SRC-DUPLICATION-001":
            snapshot["metrics"]["duplication"] = observed
        elif check_id == "SRC-DOCUMENTATION-001":
            bounded = dict(observed)
            coverage = bounded.get("coverage_percent")
            if isinstance(coverage, (int, float)):
                bounded["coverage_percent"] = min(100, coverage)
            documented = bounded.get("documented_functions")
            denominator = bounded.get("function_count")
            if isinstance(documented, int) and isinstance(denominator, int):
                bounded["documented_functions"] = min(documented, denominator)
            snapshot["metrics"]["documentation"] = bounded
        elif check_id == "SRC-DEAD-CODE-001":
            snapshot["metrics"]["dead_code"] = observed
        elif check_id in {"SRC-NATIVE-LINT-001", "SRC-NATIVE-SECURITY-001"}:
            finding = dict(observed)
            snapshot["native_findings"].append(
                {
                    "kind": "security" if check_id.endswith("SECURITY-001") else "lint",
                    "status": status,
                    **finding,
                }
            )
    return [snapshots[key] for key in sorted(snapshots)]


def _repository_practices(grouped: dict[str, list[dict[str, Any]]]) -> dict[str, bool]:
    documentation = _observed(grouped, "REPO-DOCUMENTATION-001")
    tests = _observed(grouped, "REPO-STANDARD-TESTS-001")
    ci = _observed(grouped, "REPO-VERIFICATION-CI-001")
    return {
        "README": bool(documentation.get("readme_present")),
        "Installation instructions": bool(documentation.get("installation_instructions_present")),
        "Usage example": bool(documentation.get("usage_example_present")),
        "Licence": bool(documentation.get("licence_file_present")),
        "Citation information": bool(documentation.get("citation_instructions_present")),
        "Recognized standard tests": int(tests.get("recognised_test_count") or 0) > 0,
        "Verification CI": bool(ci.get("verification_workflow_present")),
    }


def _labels(
    rows: list[dict[str, Any]], grouped: dict[str, list[dict[str, Any]]]
) -> dict[str, bool]:
    practices = _repository_practices(grouped)
    activity = _observed(grouped, "REPO-ACTIVITY-001")
    repository = not bool(activity.get("archived")) and all(practices.values())
    contract_rows = [
        row
        for row in rows
        if row.get("result_kind") == "CONTRACT" and row.get("snapshot_date") == CURRENT_DATE
    ]
    applicable = [row for row in contract_rows if row.get("status") != "NOT_APPLICABLE"]
    usage = bool(applicable) and all(row.get("status") == "PASS" for row in applicable)
    current_ids = {str(row["check_id"]) for row in rows if row.get("snapshot_date") == CURRENT_DATE}
    history_dates = {
        str(row["snapshot_date"])
        for row in rows
        if row.get("domain") == "source" and row.get("snapshot_date") in HISTORICAL_DATES
    }
    complete = (
        current_ids >= REQUIRED_CURRENT_CHECKS
        and history_dates >= set(HISTORICAL_DATES)
        and not any(str(row.get("status")) in REJECT_COVERAGE for row in rows)
    )
    return {
        "usage_exemplar": usage,
        "repository_practice_exemplar": repository,
        "complete_assessment": complete,
        "practice_exemplar": usage and repository and complete,
    }


def _public_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "check_id",
            "probe_id",
            "domain",
            "status",
            "result_kind",
            "applicability",
            "snapshot_date",
            "source_component_id",
            "executable_id",
            "expected",
            "observed",
            "command",
            "duration_seconds",
            "environment_id",
            "config_sha256",
            "evidence",
            "notes",
        )
    }


def _is_development_dependency_source(source: str) -> bool:
    parts = {part.lower() for part in Path(source).parts}
    name = Path(source).name.lower()
    return bool(parts & DEVELOPMENT_PATH_PARTS) or any(
        token in name for token in ("requirements-dev", "requirements_test", "requirements-test")
    )


def _dependency_summary(rows: list[dict[str, Any]], primary_language: str) -> dict[str, Any]:
    sources: set[str] = set()
    runtime_sources: set[str] = set()
    development_sources: set[str] = set()
    declared: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    conda_packages: dict[tuple[str, str, str], dict[str, Any]] = {}
    ecosystem_packages: dict[tuple[str, str, str], dict[str, Any]] = {}
    advisories: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    audit_errors: list[dict[str, str]] = []
    for row in rows:
        raw = row.get("observed")
        observed = raw if isinstance(raw, dict) else {}
        installed = str(row.get("probe_id")) == "dependencies:installed-environment"
        for value in observed.get("supported_sources", []):
            source = str(value)
            sources.add(source)
            if installed or not _is_development_dependency_source(source):
                runtime_sources.add(source)
            else:
                development_sources.add(source)
        for declaration in observed.get("declared_dependencies", []):
            if not isinstance(declaration, dict):
                continue
            declaration_key = (
                str(declaration.get("ecosystem")),
                str(declaration.get("role")),
                str(declaration.get("group", "")),
                str(declaration.get("name")),
                str(declaration.get("raw", "")),
            )
            declared[declaration_key] = declaration
        for package in observed.get("conda_packages", []):
            if isinstance(package, dict):
                conda_key = (
                    str(package.get("name")),
                    str(package.get("version")),
                    str(package.get("build", "")),
                )
                conda_packages[conda_key] = package
        for package in observed.get("ecosystem_packages", []):
            if isinstance(package, dict):
                ecosystem_key = (
                    str(package.get("ecosystem")),
                    str(package.get("name")),
                    str(package.get("version")),
                )
                ecosystem_packages[ecosystem_key] = package
        for advisory in observed.get("advisories", []):
            if isinstance(advisory, dict):
                advisory_key = (
                    str(advisory.get("advisory_id")),
                    str(advisory.get("dependency")),
                    str(advisory.get("resolved_version")),
                    str(advisory.get("source", "")),
                )
                advisories[advisory_key] = advisory
        if str(row.get("status", "NOT_RUN")) in REJECT_COVERAGE:
            audit_errors.append(
                {
                    "probe_id": str(row.get("probe_id", "UNKNOWN")),
                    "status": str(row.get("status", "NOT_RUN")),
                    "notes": str(row.get("notes") or "Dependency assessment did not complete."),
                }
            )
    ordered_declared = [declared[key] for key in sorted(declared)]
    ordered_conda = [conda_packages[key] for key in sorted(conda_packages)]
    ordered_ecosystem = [ecosystem_packages[key] for key in sorted(ecosystem_packages)]
    ordered_advisories = [advisories[key] for key in sorted(advisories)]
    runtime_advisories = [
        advisory
        for advisory in ordered_advisories
        if not advisory.get("source") or str(advisory["source"]) in runtime_sources
    ]
    runtime_declarations = [row for row in ordered_declared if row.get("role") == "runtime"]
    if runtime_sources:
        coverage_status = "runtime_scanned"
    elif audit_errors:
        coverage_status = "audit_error"
    elif runtime_declarations:
        coverage_status = "declared_unresolved"
    elif ordered_conda:
        coverage_status = "installed_inventory_only"
    elif development_sources:
        coverage_status = "development_only"
    else:
        coverage_status = "no_supported_input"
    return {
        "supported_sources": sorted(sources),
        "runtime_sources": sorted(runtime_sources),
        "development_sources": sorted(development_sources),
        "declared_dependencies": ordered_declared,
        "conda_packages": ordered_conda,
        "conda_package_count": len(ordered_conda),
        "ecosystem_packages": ordered_ecosystem,
        "ecosystem_package_count": len(ordered_ecosystem),
        "advisories": ordered_advisories,
        "advisory_count": len(ordered_advisories) if sources else None,
        "runtime_advisory_count": len(runtime_advisories) if runtime_sources else None,
        "runtime_advisories": runtime_advisories,
        "coverage_status": coverage_status,
        "audit_errors": audit_errors,
        "scanner_profile": (
            "Exact installed PyPI, Maven and npm packages plus CPAN Audit and supported "
            "repository lockfiles"
            if primary_language.lower() == "perl"
            else (
                "Exact installed PyPI, Maven and npm packages plus supported repository "
                "lockfiles and manifests"
            )
        ),
    }


def _dependency_status(rows: list[dict[str, Any]]) -> str:
    statuses = {str(row.get("status", "NOT_RUN")) for row in rows}
    if "ERROR" in statuses:
        return "ERROR"
    if "UNTESTABLE" in statuses:
        return "UNTESTABLE"
    if "OBSERVED" in statuses:
        return "OBSERVED"
    if "NOT_APPLICABLE" in statuses:
        return "NOT_APPLICABLE"
    return "NOT_RUN"


def _project(
    manifest: dict[str, Any], rows: list[dict[str, Any]], repository_root: Path
) -> dict[str, Any]:
    grouped = _rows_by_check(rows)
    project = manifest["project"]
    installation = manifest["installation"]
    repository = manifest["repository"]
    activity = _observed(grouped, "REPO-ACTIVITY-001")
    releases = _observed(grouped, "REPO-RELEASES-001")
    dependency_rows = [
        row
        for row in grouped.get("DEP-ADVISORY-001", [])
        if row.get("snapshot_date") == CURRENT_DATE
    ]
    return {
        "id": project["id"],
        "name": project["name"],
        "description": project["description"],
        "category": project["primary_category"],
        "tags": project["tags"],
        "included": project["include"],
        "primary_language": project["primary_language"],
        "languages": sorted(manifest["source"]["language_roots"]),
        "repository": {
            "id": repository["id"],
            "url": repository["url"],
            "snapshot_date": repository["snapshot_date"],
            "snapshot_commit": repository["snapshot_commit"],
            "activity": activity,
            "releases": releases,
            "practices": _repository_practices(grouped),
            "documentation": _observed(grouped, "REPO-DOCUMENTATION-001"),
            "standard_tests": _observed(grouped, "REPO-STANDARD-TESTS-001"),
            "verification_ci": _observed(grouped, "REPO-VERIFICATION-CI-001"),
        },
        "installation": {
            "adapter": installation["adapter"],
            "artifact": installation["artifact"],
            "version": str(installation["version"]),
            "build": installation["build"],
            "subdir": installation["subdir"],
            "artifact_sha256": installation["artifact_sha256"],
        },
        "primary_executable": manifest["interfaces"]["primary"],
        "curation_status": manifest["curation"]["status"],
        "contracts": _contract_summary(rows, repository_root),
        "source_snapshots": _source_snapshots(rows),
        "dependency_advisories": {
            "status": _dependency_status(dependency_rows),
            "observed": _dependency_summary(dependency_rows, str(project["primary_language"])),
        },
        "labels": _labels(rows, grouped),
        "results": [
            _public_result(row)
            for row in sorted(
                rows,
                key=lambda item: (
                    str(item.get("snapshot_date")),
                    str(item.get("check_id")),
                    str(item.get("probe_id")),
                ),
            )
        ],
    }


def _aggregate(projects: list[dict[str, Any]]) -> dict[str, Any]:
    primary_languages = Counter(project["primary_language"] for project in projects)
    component_languages = Counter(
        language for project in projects for language in project["languages"]
    )
    categories = Counter(project["category"] for project in projects)
    practice_counts: Counter[str] = Counter()
    dependency_coverage: Counter[str] = Counter()
    robustness: dict[str, Counter[str]] = {check_id: Counter() for check_id in ROBUSTNESS_IDS}
    rule_counts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    metric_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for project in projects:
        dependency_coverage[
            str(project["dependency_advisories"]["observed"].get("coverage_status", "audit_error"))
        ] += 1
        for practice, value in project["repository"]["practices"].items():
            if value:
                practice_counts[practice] += 1
        for contract in project["contracts"]:
            if contract["check_id"] in robustness:
                robustness[contract["check_id"]][contract["status"]] += 1
        activity = project["repository"]["activity"]
        releases = project["repository"]["releases"]
        for metric_key, value in {
            "days_since_last_commit": activity.get("days_since_last_non_bot_commit"),
            "commits_last_12_months": activity.get("commits_last_12_months"),
            "active_months_last_12_months": activity.get("active_months_last_12_months"),
            "days_since_latest_release": releases.get("days_since_latest_release"),
        }.items():
            if isinstance(value, (int, float)):
                metric_points[metric_key].append({"project_id": project["id"], "value": value})
        current_sources = [
            row for row in project["source_snapshots"] if row["snapshot_date"] == CURRENT_DATE
        ]
        for source in current_sources:
            language = source["language"]
            metrics = source["metrics"]
            mappings = {
                "production_lines": metrics.get("inventory", {}).get("physical_lines"),
                "maximum_file_lines": metrics.get("files", {}).get("maximum"),
                "percent_files_over_500": metrics.get("files", {}).get("percent_over_500"),
                "function_length_p90": metrics.get("functions", {}).get("length_percentile_90"),
                "complexity_p90": metrics.get("complexity", {}).get("percentile_90"),
                "duplication_percent": metrics.get("duplication", {}).get(
                    "duplicated_line_percent"
                ),
                "documentation_coverage": metrics.get("documentation", {}).get("coverage_percent"),
                "dead_code_candidates": metrics.get("dead_code", {}).get("candidate_count"),
            }
            for metric_key, value in mappings.items():
                if isinstance(value, (int, float)):
                    metric_points[metric_key].append(
                        {"project_id": project["id"], "language": language, "value": value}
                    )
            for finding in source["native_findings"]:
                analyzer = str(finding.get("analyzer") or "not applicable")
                value = finding.get("findings_per_kloc")
                if isinstance(value, (int, float)):
                    metric_points[f"{finding['kind']}_findings_per_kloc"].append(
                        {
                            "project_id": project["id"],
                            "language": language,
                            "analyzer": analyzer,
                            "value": value,
                        }
                    )
                for rule in finding.get("rules", []):
                    rule_id = str(rule.get("rule") or "UNKNOWN")
                    rule_key = (finding["kind"], language, analyzer, rule_id)
                    target = rule_counts.setdefault(
                        rule_key,
                        {
                            "kind": finding["kind"],
                            "language": language,
                            "analyzer": analyzer,
                            "rule": rule_id,
                            "count": 0,
                            "projects": set(),
                            "native_category": rule.get("native_category"),
                            "native_severity": rule.get("native_severity"),
                            "native_confidence": rule.get("native_confidence"),
                        },
                    )
                    target["count"] += int(rule.get("count") or 0)
                    target["projects"].add(project["id"])
        advisory_count = project["dependency_advisories"]["observed"].get("runtime_advisory_count")
        if isinstance(advisory_count, (int, float)):
            metric_points["dependency_advisories"].append(
                {"project_id": project["id"], "value": advisory_count}
            )
    rules = []
    for rule_key in sorted(rule_counts):
        row = rule_counts[rule_key]
        rules.append(
            {
                **{field: value for field, value in row.items() if field != "projects"},
                "project_count": len(row["projects"]),
                "projects": sorted(row["projects"]),
            }
        )
    return {
        "primary_language_counts": dict(sorted(primary_languages.items())),
        "component_language_counts": dict(sorted(component_languages.items())),
        "category_counts": dict(sorted(categories.items())),
        "repository_practice_counts": dict(sorted(practice_counts.items())),
        "dependency_coverage_counts": dict(sorted(dependency_coverage.items())),
        "robustness": [
            {
                "check_id": check_id,
                "label": ROBUSTNESS_IDS[check_id],
                "statuses": dict(sorted(robustness[check_id].items())),
            }
            for check_id in ROBUSTNESS_IDS
        ],
        "metric_points": dict(sorted(metric_points.items())),
        "native_rules": rules,
    }


def build_public_dataset(manifest_directory: Path, checks_path: Path) -> dict[str, Any]:
    if not checks_path.exists():
        raise ValueError(f"Normalized current results do not exist: {checks_path}")
    payload = json.loads(checks_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Normalized results must be a JSON list")
    rows_by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload:
        if row.get("run_id") == "current":
            rows_by_project[str(row["project_id"])].append(row)
    repository_root = checks_path.parents[2]
    projects = [
        _project(
            manifest,
            rows_by_project[str(manifest["project"]["id"])],
            repository_root,
        )
        for manifest in (load_yaml(path) for path in sorted(manifest_directory.glob("*.yaml")))
        if manifest["project"]["include"]
    ]
    labels = Counter(
        label for project in projects for label, active in project["labels"].items() if active
    )
    return {
        "schema_version": 2,
        "snapshot_date": CURRENT_DATE,
        "historical_snapshot_dates": HISTORICAL_DATES,
        "methodology": {
            "no_quality_score": True,
            "upstream_tests_executed": False,
            "test_source_in_code_metrics": False,
            "canonical_platform": "Linux x86-64",
            "candidate_survey_size": 1000,
            "eligible_cli_projects_found": 272,
            "first_200_eligible_reached_at_rank": 816,
            "distribution_policy": {
                "under_10": "individual points",
                "10_to_19": "box plus individual points",
                "20_or_more": "violin, box, and individual points",
            },
            "ai_context": [
                {
                    "date": "2021-06-29",
                    "label": "GitHub Copilot technical preview",
                    "url": "https://github.blog/news-insights/product-news/introducing-github-copilot-ai-pair-programmer/",
                },
                {
                    "date": "2022-11-30",
                    "label": "ChatGPT research preview",
                    "url": "https://openai.com/index/chatgpt/",
                },
                {
                    "date": "2023-03-14",
                    "label": "GPT-4 release",
                    "url": "https://openai.com/index/gpt-4-research/",
                },
            ],
        },
        "summary": {
            "assessed_projects": len(projects),
            "labels": {
                "usage_exemplars": labels["usage_exemplar"],
                "repository_practice_exemplars": labels["repository_practice_exemplar"],
                "complete_assessments": labels["complete_assessment"],
                "practice_exemplars": labels["practice_exemplar"],
            },
        },
        "aggregate": _aggregate(projects),
        "projects": projects,
    }
