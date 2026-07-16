# BMRC Python expansion execution

The authorised 20-project Python expansion uses a connected preparation phase on the
BMRC head node and an offline Slurm array. It never executes upstream project tests.

## Prepare

From a clean, committed Seebot checkout on native `x86_64` Linux:

```bash
uv run python scripts/prepare_python_expansion.py \
  --shared-root /well/aanensen/users/rva470/seebot-hpc
```

Preparation stages the current Pixi binary, every reviewed source commit, the analyzer
and project environments, and performs GitHub and
OSV-dependent observations, and hashes the immutable inputs. A temporary bundle is
promoted atomically through the `current` symlink only after all connected observations
complete without machinery `ERROR`.

## Execute

Create the Seebot-owned log directory, then submit the bounded array:

```bash
mkdir -p /well/aanensen/users/rva470/seebot-hpc/logs
sbatch scripts/slurm/run_python_expansion.sbatch
```

Each array task verifies its staged inputs, selects exactly one committed project ID,
uses task-private scratch, and runs source, history, usage, and robustness observations
with `SEEBOT_OFFLINE=1`. BMRC compute nodes have no external network route; Slurm applies
two CPUs and 8 GiB memory, and the runner applies a 256-process limit.

## Collect

Only after every task and project validator succeeds, normalize from the shared bundle:

```bash
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  results normalize
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  results rebuild-global
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  report build
```

Publication remains blocked until the complete 30-project inventory audit and repository
release gate pass. Preserve the promoted bundle and evidence; remove only abandoned
Seebot-owned preparation and task-scratch paths.
