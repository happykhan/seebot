"""Verified source download and path-traversal-safe archive extraction."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import httpx

from seebot.evidence import sha256_file


class ChecksumMismatchError(ValueError):
    """Downloaded content did not match the recipe checksum."""


def download_verified(url: str, destination: Path, expected_sha256: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    actual = sha256_file(destination)
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise ChecksumMismatchError(f"Expected {expected_sha256}, received {actual}")
    return destination


def _safe_target(root: Path, member_name: str) -> Path:
    target = (root / member_name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Unsafe archive member: {member_name}")
    return target


def extract_safe(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as handle:
            for member in handle.getmembers():
                _safe_target(destination, member.name)
                if member.issym() or member.islnk():
                    raise ValueError(f"Links are not extracted: {member.name}")
            handle.extractall(destination, filter="data")
        return
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as handle:
            for zip_member in handle.infolist():
                _safe_target(destination, zip_member.filename)
            handle.extractall(destination)
        return
    raise ValueError(f"Unsupported source archive: {archive}")
