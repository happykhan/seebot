"""Deterministic project-manifest selection for surveys and reruns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seebot.manifests import load_yaml


def manifest_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*.yaml"))


def select_manifests(
    root: Path,
    *,
    tools: list[str] | None = None,
    categories: list[str] | None = None,
    languages: list[str] | None = None,
    include_excluded: bool = False,
) -> list[tuple[Path, dict[str, Any]]]:
    requested_tools = set(tools or [])
    requested_categories = set(categories or [])
    requested_languages = set(languages or [])
    selected: list[tuple[Path, dict[str, Any]]] = []
    for path in manifest_paths(root):
        manifest = load_yaml(path)
        project = manifest["project"]
        if not include_excluded and not project["include"]:
            continue
        if requested_tools and project["id"] not in requested_tools:
            continue
        if requested_categories and project["primary_category"] not in requested_categories:
            continue
        observed_languages = set(manifest["source"]["language_roots"])
        if requested_languages and not requested_languages.intersection(observed_languages):
            continue
        selected.append((path, manifest))
    missing = requested_tools - {manifest["project"]["id"] for _, manifest in selected}
    if missing:
        raise ValueError("Unknown or excluded project(s): " + ", ".join(sorted(missing)))
    return selected
