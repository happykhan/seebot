# BMRC Python expansion execution

The authorised 20-project Python expansion uses a connected preparation phase on the
BMRC head node and an offline Slurm array. It never executes upstream project tests.

## Prepare

From a clean, committed Seebot checkout on native `x86_64` Linux:

```bash
uv run python scripts/prepare_python_expansion.py \
  --shared-root /well/aanensen/users/rva470/seebot-hpc \
  --jobs 4
```

Preparation stages the current Pixi binary, every reviewed source commit, the source-analyzer
environment, and the 20 project environments. It checks each source checkout with
`git rev-parse HEAD`; it does not hash source files or Git indexes. Hashing is limited to small
configuration, manifest, executable, and lockfile inputs. It also does not build the unused
dependency-only analyzer profile.
The Pixi executable is hashed once during preparation; array tasks only check that it is present
and executable. Repeated runtime and audit-code identities are cached once per worker process.
`PREPARED.json` marks the bundle ready only after preparation completes.
The connected preparation phase uses a conservative four workers for source snapshot downloads
and, after the shared analyzer profile is ready, four workers for the independent Pixi project
environments. This improves on serial preparation without monopolizing the shared head node.
`--jobs` is an explicit override and does not change results.
Preparation now refuses to reuse a marked bundle if any project or analyzer environment is
missing. Preserve such a bundle for evidence, prepare a replacement under a new shared root,
and point the submitted job at it explicitly:

```bash
uv run python scripts/prepare_python_expansion.py \
  --shared-root /well/aanensen/users/rva470/seebot-hpc-next \
  --jobs 4
sbatch --export=ALL,SEEBOT_RUN_ROOT=/well/aanensen/users/rva470/seebot-hpc-next/current \
  scripts/slurm/run_python_expansion.sbatch
```

## Execute

Create the Seebot-owned log directory, then submit the bounded array:

```bash
mkdir -p /well/aanensen/users/rva470/seebot-hpc/logs
sbatch scripts/slurm/run_python_expansion.sbatch
```

Each array task verifies its staged inputs, selects exactly one committed project ID,
uses task-private scratch, and runs current/historical source, usage, and robustness observations
with `SEEBOT_OFFLINE=1`. Immutable prepared snapshots are read in place instead of being
copied to scratch once per historical date. BMRC compute nodes have no external network
route. During beta tuning, Slurm assigns eight CPUs and 16 GiB memory to each project,
Pylint uses all eight CPUs, the array permits 20 concurrent projects, and the runner applies
a 256-process limit. The complete array can therefore use up to 160 of the account's 600 CPUs.

`--check history` already includes both historical and current source snapshots, so the task
does not also request the redundant `source` selector. Input verification and output
validation remain separate: the first detects damaged prepared machinery before execution;
the second checks completeness, schemas, and prohibited upstream-test commands afterwards.
Historical snapshots run only the structural measurements displayed in the website's source
history. Pylint and the other native analyzers run once, on current source.

## Performance baseline

Slurm accounting for forced run `24308472` on 16 July 2026 showed 20 project tasks consuming
6,706 wall-clock task-seconds but 1,766 CPU-seconds: 13% of the two allocated CPUs. Individual
tasks read 2.6-7.2 GB and the scheduler started the first wave after 16 seconds. The dominant
delay was therefore repeated shared-filesystem reads plus the previous four-task array
throttle, not queue latency or memory pressure (observed peak RSS was 1.27 GB). The account's
normal QoS permits 600 CPUs; all 20 tasks require 40 CPUs, so the bounded array now permits
all projects to run concurrently. With the recorded task durations, its scheduler-only
lower-bound makespan is 11:28 versus 29:21 at four ways. Treat that as a planning estimate:
the shared partition's load can delay task starts, and the bounded rerun still needs to
confirm that the in-place snapshot change removed the previous filesystem bottleneck.

The remaining work is intentional rather than orchestration overhead. The 20 projects cover
120 dated source observations and currently produce 1,360 source rows, 160 robustness rows,
and 97 usage rows. The source analyzers account for about 2,027 recorded process-seconds.
Removing those runs, combining dated observations, or sharing installed environments between
projects would change the assessment or its isolation. Preparation therefore remains a
connected install-and-stage phase, followed by one independent offline task per project.

## Collect

Only after every task and project validator succeeds, normalize from the shared bundle:

```bash
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  results normalize
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  results rebuild-global
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  report build
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  results compact-evidence
uv run seebot --output-directory /well/aanensen/users/rva470/seebot-hpc/current \
  results compact-evidence --yes
```

The first compaction command is a dry-run inventory. The second removes the complete per-check
evidence tree after its normalized summaries and website excerpts have been generated. During
beta development, rerun the audit if those intermediates are needed again.

Publication remains blocked until the complete 30-project inventory audit and repository
release gate pass. Preserve the promoted bundle and evidence; remove only abandoned
Seebot-owned preparation and task-scratch paths.
