#!/usr/bin/env bash
#SBATCH --job-name=seebot-python
#SBATCH --partition=short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --array=0-19%4
#SBATCH --output=/well/aanensen/users/rva470/seebot-hpc/logs/%A_%a.out
#SBATCH --error=/well/aanensen/users/rva470/seebot-hpc/logs/%A_%a.err

set -euo pipefail

repo=/well/aanensen/users/rva470/seebot
run_root=/well/aanensen/users/rva470/seebot-hpc/current
project=$(awk -v task_id="$SLURM_ARRAY_TASK_ID" '$1 == task_id { print $2 }' "$run_root/array.tsv")
if [[ -z "$project" ]]; then
  echo "No project mapped for array index $SLURM_ARRAY_TASK_ID" >&2
  exit 64
fi

scratch="${TMPDIR:-/tmp}/seebot-${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
mkdir -p "$scratch"
trap 'rm -rf "$scratch"' EXIT

export SEEBOT_CONTAINER_RUNTIME=native
export SEEBOT_PIXI_EXECUTABLE="$run_root/tools/pixi"
export SEEBOT_OFFLINE=1
export SEEBOT_SKIP_STORAGE_BUDGET=1
export SEEBOT_SNAPSHOT_ROOT="$run_root/snapshots"
export SEEBOT_WORK_ROOT="$scratch"

cd "$repo"
"$repo/.seebot-cache/bin/uv" run python scripts/verify_prepared_bundle.py \
  --root "$run_root" --project "$project"
"$repo/.seebot-cache/bin/uv" run seebot --output-directory "$run_root" \
  audit run --tool "$project" --check source --check history --check usage --check robustness
"$repo/.seebot-cache/bin/uv" run python scripts/validate_project_evidence.py \
  --root "$run_root" --project "$project"
