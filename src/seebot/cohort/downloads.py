"""Discover and retrieve complete months from Anaconda's official dataset."""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

BASE_URL = "https://anaconda-package-data.s3.amazonaws.com/conda/hourly"


@dataclass(frozen=True)
class DailyObject:
    day: str
    url: str
    etag: str | None
    size_bytes: int | None


def month_urls(year: int, month: int) -> list[tuple[date, str]]:
    count = calendar.monthrange(year, month)[1]
    return [
        (
            date(year, month, day),
            f"{BASE_URL}/{year:04d}/{month:02d}/{year:04d}-{month:02d}-{day:02d}.parquet",
        )
        for day in range(1, count + 1)
    ]


def window_urls(start: date, end: date) -> list[tuple[date, str]]:
    if end < start:
        raise ValueError("Download window end precedes its start")
    values: list[tuple[date, str]] = []
    cursor = start
    while cursor <= end:
        values.append(
            (
                cursor,
                f"{BASE_URL}/{cursor:%Y/%m}/{cursor:%Y-%m-%d}.parquet",
            )
        )
        cursor += timedelta(days=1)
    return values


def inspect_window(start: date, end: date) -> list[DailyObject]:
    """Record official object identities without retaining the Parquet payloads."""
    objects: list[DailyObject] = []
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for day, url in window_urls(start, end):
            response = client.head(url)
            if response.status_code != 200:
                raise RuntimeError(f"Official download object unavailable: {url}")
            size = response.headers.get("content-length")
            objects.append(
                DailyObject(
                    day=day.isoformat(),
                    url=url,
                    etag=response.headers.get("etag", "").strip('"') or None,
                    size_bytes=int(size) if size else None,
                )
            )
    return objects


def write_object_manifest(objects: list[DailyObject], output: Path) -> dict[str, object]:
    if not objects:
        raise ValueError("Cannot write an empty official-object manifest")
    manifest: dict[str, object] = {
        "schema_version": 2,
        "period_start": objects[0].day,
        "period_end": objects[-1].day,
        "retrieved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "objects": [asdict(item) for item in objects],
    }
    canonical = json.dumps(manifest, sort_keys=True).encode()
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def previous_month(value: date) -> date:
    return date(value.year - (value.month == 1), 12 if value.month == 1 else value.month - 1, 1)


def inspect_month(client: httpx.Client, year: int, month: int) -> list[DailyObject] | None:
    objects: list[DailyObject] = []
    for day, url in month_urls(year, month):
        response = client.head(url)
        if response.status_code != 200:
            return None
        size = response.headers.get("content-length")
        objects.append(
            DailyObject(
                day=day.isoformat(),
                url=url,
                etag=response.headers.get("etag", "").strip('"') or None,
                size_bytes=int(size) if size else None,
            )
        )
    return objects


def latest_complete_month(today: date | None = None) -> tuple[date, list[DailyObject]]:
    cursor = previous_month((today or datetime.now(UTC).date()).replace(day=1))
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for _ in range(36):
            objects = inspect_month(client, cursor.year, cursor.month)
            if objects is not None:
                return cursor, objects
            cursor = previous_month(cursor)
    raise RuntimeError("No complete Anaconda download-data month found in the last 36 months")


def complete_window(end_month: date, months: int) -> list[date]:
    values = [end_month]
    while len(values) < months:
        values.append(previous_month(values[-1]))
    return list(reversed(values))


def fetch_window(output: Path, *, months: int = 12, dry_run: bool = False) -> dict[str, object]:
    end_month, end_objects = latest_complete_month()
    window = complete_window(end_month, months)
    all_objects: list[DailyObject] = []
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        for month in window:
            objects = (
                end_objects
                if month == end_month
                else inspect_month(client, month.year, month.month)
            )
            if objects is None:
                raise RuntimeError(f"Incomplete month inside selected window: {month:%Y-%m}")
            all_objects.extend(objects)
            if dry_run:
                continue
            for item in objects:
                target = output / item.day[:4] / item.day[5:7] / f"{item.day}.parquet"
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with client.stream("GET", item.url) as response:
                    response.raise_for_status()
                    with target.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            handle.write(chunk)
    manifest = {
        "schema_version": 1,
        "period_start": all_objects[0].day,
        "period_end": all_objects[-1].day,
        "retrieved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "objects": [asdict(item) for item in all_objects],
    }
    canonical = json.dumps(manifest, sort_keys=True).encode()
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
        (output / "download-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    return manifest
