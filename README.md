# Seebot

Seebot is a reproducible observatory for scientific command-line software. It publishes
separate observations about public GitHub repositories, production source code, installed
interfaces, and deliberately awkward input. It does not produce an overall quality score,
ranking, medal, or scientific-validity judgement.

The current published dataset contains ten independently curated projects spanning Python,
Cython, Perl, C, C++, Rust, and Java. Their canonical repository snapshot is the commit at
or before 1 July 2026. Source-only history uses the commits at or before 1 July from 2021
through 2025 where each project existed.

Bioconda download records are used only to discover candidate tools, and Pixi is the first
generic installation adapter. Packages, recipes, download counts, and installer behaviour
are not project-health metrics.

## What Seebot records

- Repository practices: activity and release recency, documentation, licence, citation,
  recognized standard tests, and verification CI.
- Production source: source and file sizes, function structure, complexity, duplication,
  documentation coverage, native linter rules, source-security indicators, dead-code
  candidates, and current supported dependency advisories.
- Installed behaviour: help and version interfaces, no-argument behaviour, one miniature
  valid run, stdin/stdout support where applicable, and seven invalid-input scenarios.

Seebot detects standard upstream tests but never executes them. Test source, generated
code, vendored code, build output, examples, documentation, fixtures, and data are excluded
from code-health denominators.

## Install and validate Seebot

```bash
make install
make check
```

`make check` runs Seebot's own tests and validators. It does not run assessed projects'
test suites.

## Select exactly what to rerun

Plan work without installing or executing an assessed tool:

```bash
uv run seebot audit plan --tool cutadapt --check usage --check robustness
uv run seebot history plan --tool cutadapt --year 2023
```

Run one project or repeat `--tool` to run a chosen set:

```bash
uv run seebot --force audit run --tool cutadapt --check usage --check robustness
uv run seebot --force audit run --tool samtools --tool bcftools --check repository --check source
```

Without `--force`, completed evidence is reused. A forced run overwrites current generated
evidence; Seebot does not maintain parallel result versions during this phase.

Normalize observations and rebuild the website dataset:

```bash
uv run seebot results normalize
uv run seebot report build
cd web && npm run build
```

Inspect or remove only Seebot-owned temporary storage:

```bash
uv run seebot cache status
uv run seebot cache prune --yes
```

## Factual exemplar labels

Seebot can derive four transparent labels: Usage exemplar, Repository-practice exemplar,
Complete assessment, and Practice exemplar. Code-health values never qualify or disqualify
a project. Labels are derived observations, not prizes or editorial judgements.

## Documentation

- [Protocol](docs/protocol.md)
- [Assessment catalogue](docs/rubric.md)
- [Assessment specification](docs/assessment-specification.md)
- [Cohort and discovery evidence](docs/cohort.md)
- [Data dictionary](docs/data-dictionary.md)
- [Limitations](docs/limitations.md)
