"""Build language-scoped comparative profiles from normalized observations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

LANGUAGE_DOMAINS = {"python", "perl", "c", "cpp", "rust"}

METRICS: dict[str, tuple[str, str, bool, str]] = {
    "PY-RUFF-001": ("finding_count", "Ruff findings", False, "count"),
    "PY-PYLINT-001": ("message_count", "Pylint messages", False, "count"),
    "PY-RADON-001": ("complexity_mean", "Mean cyclomatic complexity", False, "raw"),
    "PY-INTERROGATE-001": ("docstring_coverage_percent", "Docstring coverage", True, "percent"),
    "PY-VULTURE-001": ("candidate_count", "Dead-code candidates", False, "count"),
    "PY-BANDIT-001": ("indicator_count", "Security indicators", False, "count"),
    "PERL-CRITIC-001": ("finding_count", "Perl::Critic findings", False, "count"),
    "C-CLANGTIDY-001": ("diagnostic_count", "clang-tidy diagnostics", False, "count"),
    "CPP-CLANGTIDY-001": ("diagnostic_count", "clang-tidy diagnostics", False, "count"),
    "C-CPPCHECK-001": ("finding_count", "Cppcheck findings", False, "count"),
    "CPP-CPPCHECK-001": ("finding_count", "Cppcheck findings", False, "count"),
    "RS-CLIPPY-001": ("diagnostic_count", "Clippy diagnostics", False, "count"),
    "RS-UNSAFE-001": ("unsafe_count", "Unsafe-code indicators", False, "count"),
}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _metric(row: dict[str, Any]) -> dict[str, Any] | None:
    definition = METRICS.get(row["check_id"])
    if not definition or row["status"] != "PASS":
        return None
    field, label, higher_is_better, unit = definition
    value = _number(row["observed"].get(field))
    if value is None:
        return None
    if unit == "count":
        lines = _number(row["observed"].get("nonblank_noncomment_lines"))
        if lines:
            value = value * 1000 / lines
            unit = "per 1k lines"
        else:
            unit = "count"
    return {
        "check_id": row["check_id"],
        "label": label,
        "value": value,
        "unit": unit,
        "higher_is_better": higher_is_better,
    }


def build_profiles(
    packages: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    minimum_provisional: int = 3,
    minimum_classified: int = 10,
    version: str = "unversioned",
) -> dict[str, Any]:
    active_runs = {package["package_id"]: package["run_id"] for package in packages}
    metrics: dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    by_package: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if (
            active_runs.get(row["package_id"]) != row["run_id"]
            or row["domain"] not in LANGUAGE_DOMAINS
        ):
            continue
        parsed = _metric(row)
        if parsed:
            language = row["domain"]
            metrics[(language, row["check_id"], row["config_sha256"])].append(
                (row["package_id"], parsed)
            )
            by_package[row["package_id"]][language].append(parsed)
    output: list[dict[str, Any]] = []
    for package in packages:
        languages = []
        configured = package.get("languages", [])
        for language in configured:
            package_metrics = by_package[package["package_id"]].get(language, [])
            interpreted = []
            for item in package_metrics:
                row = next(
                    r
                    for r in rows
                    if r["package_id"] == package["package_id"]
                    and r["run_id"] == package["run_id"]
                    and r["check_id"] == item["check_id"]
                )
                cohort = metrics[(language, item["check_id"], row["config_sha256"])]
                ordered = sorted(value["value"] for _, value in cohort)
                n = len(ordered)
                rank = sum(value <= item["value"] for value in ordered)
                percentile = 100 * (rank - 0.5) / n if n >= minimum_provisional else None
                direction = (
                    percentile
                    if item["higher_is_better"]
                    else (100 - percentile if percentile is not None else None)
                )
                if n < minimum_provisional:
                    label = "insufficient"
                elif n < minimum_classified:
                    label = "provisional"
                elif direction is not None and direction >= 75:
                    label = "favourable"
                elif direction is not None and direction <= 25:
                    label = "unfavourable"
                else:
                    label = "typical"
                interpreted.append(
                    item | {"cohort_size": n, "percentile": percentile, "interpretation": label}
                )
            languages.append(
                {"language": language, "metrics": interpreted, "measured_count": len(interpreted)}
            )
        output.append({"package_id": package["package_id"], "languages": languages})
    return {
        "schema_version": 1,
        "interpretation_version": version,
        "comparison_policy": "same-language-and-config-only",
        "minimum_provisional_cohort": minimum_provisional,
        "minimum_classified_cohort": minimum_classified,
        "profiles": output,
    }
