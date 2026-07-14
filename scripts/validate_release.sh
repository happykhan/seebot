#!/usr/bin/env bash
set -euo pipefail
make check
if find . -path './.git' -prune -o -type f -size +25M -print | grep -q .; then
  echo "Release rejected: tracked workspace contains a file larger than 25 MB." >&2
  exit 1
fi

