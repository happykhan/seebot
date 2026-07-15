import json
from pathlib import Path

from jsonschema import Draft202012Validator

from seebot.report.awards import badge_svg, rank_packages, score_package

CONFIG = {
    "maximum_points": 100,
    "categories": {
        "testing": {"signals": {"tests": 25}},
        "automation": {"signals": {"ci": 20}},
        "documentation": {"signals": {"docs": 20}},
        "stewardship": {"signals": {"licence": 20}},
        "reproducibility": {"signals": {"manifest": 15}},
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
        "testing": 25,
        "automation": 20,
        "documentation": 20,
        "stewardship": 20,
        "reproducibility": 15,
    }
    assert score["tier"] == "Gold"
    assert score["eligible"] is True


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
