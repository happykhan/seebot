from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from seebot.cohort.downloads import complete_window, month_urls, window_urls
from seebot.cohort.rank import rank_downloads, rank_remote_downloads


def test_complete_window_is_chronological_across_year_boundary() -> None:
    assert complete_window(date(2026, 2, 1), 4) == [
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 2, 1),
    ]
    assert len(month_urls(2024, 2)) == 29
    fixed = window_urls(date(2025, 7, 1), date(2026, 6, 30))
    assert len(fixed) == 365
    assert fixed[0][0] == date(2025, 7, 1)
    assert fixed[-1][0] == date(2026, 6, 30)


def test_rank_aggregates_across_package_dimensions(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    table = pa.table(
        {
            "data_source": ["bioconda", "bioconda", "bioconda", "conda-forge"],
            "pkg_name": ["alpha", "alpha", "beta", "noise"],
            "pkg_version": ["1", "2", "1", "1"],
            "pkg_platform": ["linux-64", "noarch", "linux-64", "linux-64"],
            "pkg_python": ["3.12", None, None, None],
            "counts": [10, 5, 7, 1000],
        }
    )
    pq.write_table(table, raw / "day.parquet")
    output = tmp_path / "cohort.csv"
    query_hash = rank_downloads(raw, output, "bioconda", 300)
    assert len(query_hash) == 64
    lines = output.read_text().splitlines()
    assert lines[1].startswith("1,alpha,15")
    assert lines[2].startswith("2,beta,7")

    remote_output = tmp_path / "cohort-remote.csv"
    remote_hash = rank_remote_downloads(
        [
            {
                "day": "2026-06-30",
                "url": (raw / "day.parquet").resolve().as_uri(),
                "etag": "fixture",
                "size_bytes": (raw / "day.parquet").stat().st_size,
            }
        ],
        remote_output,
        "bioconda",
        300,
    )
    assert len(remote_hash) == 64
    assert remote_output.read_text().splitlines()[1].startswith("1,alpha,15")
