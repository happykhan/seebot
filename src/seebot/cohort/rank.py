"""Deterministic aggregation of local official Parquet inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path

QUERY = """
COPY (
  SELECT
    row_number() OVER (ORDER BY sum(counts) DESC, pkg_name ASC) AS candidate_rank,
    pkg_name,
    CAST(sum(counts) AS BIGINT) AS download_count
  FROM read_parquet($files)
  WHERE data_source = $channel
  GROUP BY pkg_name
  ORDER BY download_count DESC, pkg_name ASC
  LIMIT $top
) TO $output (HEADER, DELIMITER ',');
""".strip()


def rank_downloads(raw_directory: Path, output: Path, channel: str, top: int) -> str:
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - exercised without cohort extra
        raise RuntimeError("Install Seebot's cohort extra: uv sync --extra cohort") from exc
    files = sorted(str(path) for path in raw_directory.rglob("*.parquet"))
    if not files:
        raise ValueError(f"No Parquet inputs found under {raw_directory}")
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute(
        QUERY,
        {"files": files, "channel": channel, "top": top, "output": str(output)},
    )
    query_identity = QUERY + "\n" + "\n".join(files) + f"\n{channel}\n{top}\n"
    return hashlib.sha256(query_identity.encode()).hexdigest()


def rank_remote_downloads(
    objects: list[dict[str, object]], output: Path, channel: str, top: int
) -> str:
    """Aggregate official Parquet URLs without retaining their large payloads."""
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install Seebot's cohort extra: uv sync --extra cohort") from exc
    urls = [str(row["url"]) for row in objects]
    if not urls:
        raise ValueError("Official-object manifest contains no URLs")
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute(
        QUERY,
        {"files": urls, "channel": channel, "top": top, "output": str(output)},
    )
    identities = [
        f"{row.get('day')}|{row.get('url')}|{row.get('etag')}|{row.get('size_bytes')}"
        for row in objects
    ]
    query_identity = QUERY + "\n" + "\n".join(identities) + f"\n{channel}\n{top}\n"
    return hashlib.sha256(query_identity.encode()).hexdigest()
