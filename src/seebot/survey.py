"""Metadata-first project/interface survey rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seebot.selection import select_manifests

SURVEY_FIELDS = (
    "project_id",
    "project_name",
    "download_rank",
    "repository_url",
    "included",
    "exclusion_code",
    "primary_category",
    "languages",
    "primary_executable",
    "executables",
    "stdin_support",
    "stdout_support",
    "valid_run_status",
    "fixture_ids",
    "curation_status",
)


def survey_rows(
    manifest_root: Path,
    *,
    tools: list[str] | None = None,
    categories: list[str] | None = None,
    languages: list[str] | None = None,
    include_excluded: bool = True,
) -> list[dict[str, Any]]:
    selected = select_manifests(
        manifest_root,
        tools=tools,
        categories=categories,
        languages=languages,
        include_excluded=include_excluded,
    )
    rows: list[dict[str, Any]] = []
    for _, manifest in selected:
        project = manifest["project"]
        interface = manifest["interfaces"]
        rows.append(
            {
                "project_id": project["id"],
                "project_name": project["name"],
                "download_rank": manifest["discovery"]["rank"],
                "repository_url": manifest["repository"]["url"],
                "included": project["include"],
                "exclusion_code": project["exclusion_code"],
                "primary_category": project["primary_category"],
                "languages": ";".join(sorted(manifest["source"]["language_roots"])),
                "primary_executable": interface["primary"],
                "executables": ";".join(interface["executables"]),
                "stdin_support": interface["stdin_support"],
                "stdout_support": interface["stdout_support"],
                "valid_run_status": manifest["valid_run"]["status"],
                "fixture_ids": ";".join(manifest["valid_run"]["fixture_ids"]),
                "curation_status": manifest["curation"]["status"],
            }
        )
    return rows
