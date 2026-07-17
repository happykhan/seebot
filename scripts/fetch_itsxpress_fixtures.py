#!/usr/bin/env python3
"""Fetch the tiny public paired ITSxpress example at its reviewed commit."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "ff381caaba42801500e7bdc8e242ba55efb94898"
BASE_URL = f"https://raw.githubusercontent.com/usda-ars-gbru/itsxpress/{COMMIT}/tests/test_data"
FILES = {
    "4774-1-MSITS3_R1.fastq": "21bc0f3ddcd7222fdc76e50e12b86c8783d7d14329b11b2bfbbb34ffe211d36e",
    "4774-1-MSITS3_R2.fastq": "242461702a959fabd9f9669105d045c53345ccaa3f0a00265ceac69c3d7d272c",
}


def main() -> None:
    target = ROOT / "fixtures" / "itsxpress"
    target.mkdir(parents=True, exist_ok=True)
    for name, expected_hash in FILES.items():
        with urllib.request.urlopen(f"{BASE_URL}/{name}", timeout=60) as response:
            payload = response.read()
        observed_hash = hashlib.sha256(payload).hexdigest()
        if observed_hash != expected_hash:
            raise ValueError(f"Unexpected SHA-256 for {name}: {observed_hash}")
        (target / name).write_bytes(payload)


if __name__ == "__main__":
    main()
