#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: $0 PACKAGE_OR_MANIFEST RUN_ID" >&2
  exit 64
fi
uv run seebot --run-id "$2" audit all "$1"
