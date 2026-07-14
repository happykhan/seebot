#!/usr/bin/env bash
set -euo pipefail
uv run seebot manifest validate-all
uv run pytest
echo "Pilot gate remains locked until ten reviewed package manifests are present."
