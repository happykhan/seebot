"""Transparent award scoring and static badge generation."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml


def load_award_config(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def score_package(rows: list[dict[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    by_check = {row["check_id"]: row for row in rows}
    missing: list[str] = []
    repository = by_check.get("REPO-PRACTICES-001")
    if repository is None or repository["status"] != "PASS":
        missing.append("REPO-PRACTICES-001")
    breakdown = {
        category: round(
            sum(
                float(points)
                for signal, points in definition["signals"].items()
                if repository is not None
                and repository["status"] == "PASS"
                and repository["observed"].get(signal) is True
            ),
            1,
        )
        for category, definition in config["categories"].items()
    }
    score = sum(breakdown.values())
    tier = next(tier for tier in config["tiers"] if score >= float(tier["minimum_points"]))
    return {
        "score": round(score, 1),
        "maximum_points": config["maximum_points"],
        "eligible": not missing,
        "missing_checks": sorted(set(missing)),
        "tier": tier["name"],
        "tier_colour": tier["colour"],
        "breakdown": breakdown,
    }


def rank_packages(
    packages: list[dict[str, Any]], rows: list[dict[str, Any]], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows_by_package: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_package.setdefault(row["package_id"], []).append(row)
    rankings = [
        {**package, **score_package(rows_by_package.get(package["package_id"], []), config)}
        for package in packages
    ]
    rankings.sort(key=lambda item: (not item["eligible"], -item["score"], item["name"]))
    previous_score: float | None = None
    previous_rank = 0
    for position, item in enumerate(rankings, start=1):
        if not item["eligible"]:
            item["rank"] = None
            continue
        if item["score"] != previous_score:
            previous_rank = position
            previous_score = item["score"]
        item["rank"] = previous_rank
    return rankings


def badge_svg(name: str, tier: str, score: float, colour: str) -> str:
    """Return a compact, dependency-free SVG badge."""
    label = "Seebot"
    value = f"{tier} {score:g}/100"
    label_width = 62
    value_width = max(92, 7 * len(value) + 16)
    total = label_width + value_width
    safe_name = html.escape(name)
    safe_value = html.escape(value)
    safe_colour = html.escape(colour)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20"
  role="img" aria-label="{safe_name}: {safe_value}">
  <title>{safe_name}: {safe_value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".16"/>
    <stop offset="1" stop-opacity=".08"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#26302c"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{safe_colour}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Arial,sans-serif"
    font-size="11">
    <text x="{label_width / 2:g}" y="15">{label}</text>
    <text x="{label_width + value_width / 2:g}" y="15">{safe_value}</text>
  </g>
</svg>
"""


def write_badges(rankings: list[dict[str, Any]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for item in rankings:
        slug = re.sub(r"[^a-z0-9._-]+", "-", item["name"].lower()).strip("-")
        (output / f"{slug}.svg").write_text(
            badge_svg(item["name"], item["tier"], item["score"], item["tier_colour"]),
            encoding="utf-8",
        )
