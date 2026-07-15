#!/usr/bin/env bash
set -euo pipefail

uv run seebot manifest validate-all
uv run seebot fixture validate

if [[ "${1:-}" == "--dry-run" ]]; then
  uv run seebot audit plan
  exit 0
fi

uv run seebot audit run "$@"
