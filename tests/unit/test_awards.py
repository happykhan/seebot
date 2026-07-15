import json
from pathlib import Path

from jsonschema import Draft202012Validator

from seebot.report.awards import badge_svg, rank_packages, score_package

CONFIG = {
    "maximum_points": 100,
    "minimum_coverage": 0.8,
    "categories": {
        "testing": {
            "maximum_points": 30,
            "signals": [{"id": "tests", "source": "repository", "key": "tests", "points": 30}],
        },
        "documentation": {
            "maximum_points": 25,
            "signals": [{"id": "docs", "source": "repository", "key": "docs", "points": 25}],
        },
        "reproducibility": {
            "maximum_points": 20,
            "signals": [
                {"id": "manifest", "source": "repository", "key": "manifest", "points": 20}
            ],
        },
        "automation": {
            "maximum_points": 15,
            "signals": [{"id": "ci", "source": "repository", "key": "ci", "points": 15}],
        },
        "reuse_attribution": {
            "maximum_points": 10,
            "signals": [{"id": "licence", "source": "repository", "key": "licence", "points": 10}],
        },
    },
    "tiers": [
        {"name": "Gold", "minimum_points": 85, "colour": "gold"},
        {"name": "Reviewed", "minimum_points": 0, "colour": "grey"},
    ],
}


def rows(package_id: str) -> list[dict[str, object]]:
    return [
        {
            "package_id": package_id,
            "check_id": "REPO-PRACTICES-001",
            "status": "PASS",
            "observed": {
                "licence": True,
                "tests": True,
                "ci": True,
                "docs": True,
                "manifest": True,
            },
        },
    ]


def test_scores_transparent_components() -> None:
    score = score_package(rows("tool"), CONFIG)
    assert score["score"] == 100
    assert score["breakdown"] == {
        "testing": 30,
        "documentation": 25,
        "reproducibility": 20,
        "automation": 15,
        "reuse_attribution": 10,
    }
    assert score["assessment_coverage"] == 1
    assert score["tier"] == "Gold"
    assert score["eligible"] is True


def test_unknown_signal_reduces_coverage_without_becoming_failure() -> None:
    incomplete = rows("tool")
    incomplete[0]["observed"].pop("docs")
    score = score_package(incomplete, CONFIG)
    assert score["breakdown"]["documentation"] == 0
    assert score["category_coverage"]["documentation"] == 0
    assert "documentation.docs" in score["unknown_signals"]
    assert score["assessment_coverage"] == 0.75
    assert score["eligible"] is False


def test_competition_ranking_preserves_ties() -> None:
    packages = [
        {"package_id": "b", "name": "beta"},
        {"package_id": "a", "name": "alpha"},
    ]
    ranked = rank_packages(packages, rows("a") + rows("b"), CONFIG)
    assert [(item["name"], item["rank"]) for item in ranked] == [("alpha", 1), ("beta", 1)]


def test_badge_escapes_package_name() -> None:
    badge = badge_svg("tool<script>", "Gold", 90, "#123456")
    assert "tool&lt;script&gt;" in badge
    assert "tool<script>" not in badge


def test_published_ranking_view_matches_schema() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "schemas" / "rankings.schema.json").read_text())
    ranking = json.loads((root / "web" / "public" / "data" / "rankings.json").read_text())
    Draft202012Validator(schema).validate(ranking)
