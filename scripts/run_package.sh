#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "usage: $0 TOOL [SEEBOT AUDIT OPTIONS...]" >&2
  exit 64
fi
tool="$1"
shift
uv run seebot --force audit run --tool "$tool" "$@"
