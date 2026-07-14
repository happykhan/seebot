"""Deterministic CLI fixture used to test Seebot itself."""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="healthy-tool")
    parser.add_argument("--version", action="version", version="healthy-tool 1.0.0")
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
