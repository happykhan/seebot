"""Retrieve immutable recipe files from a pinned bioconda-recipes commit."""

from __future__ import annotations

from pathlib import Path

import httpx


def fetch_recipe_file(commit: str, recipe_path: str, destination: Path) -> Path:
    url = (
        "https://raw.githubusercontent.com/bioconda/bioconda-recipes/"
        f"{commit}/{recipe_path}/meta.yaml"
    )
    response = httpx.get(url, follow_redirects=True, timeout=60)
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return destination
