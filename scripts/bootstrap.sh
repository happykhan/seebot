#!/usr/bin/env bash
set -euo pipefail
uv sync --all-extras
npm --prefix web ci

