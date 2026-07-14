# SeeBot

**Study title:** *SeeBot: a reproducible audit of software-engineering practices in widely downloaded Bioconda tools*

SeeBot is a code-first research project for selecting a frozen cohort of Bioconda packages, retrieving the exact packaged source, running conservative and reproducible checks, preserving evidence, and publishing analysis-ready results through a web application.

The project measures observable properties. It does not label software as “good” or “bad”, infer scientific validity from engineering signals, or collapse distinct domains into a single quality score.

## Current phase

SeeBot is in the **10-package pilot** phase. The 200-package study must not start until the pilot is reproducible and its schemas, exclusion vocabulary, and rubric have been frozen through a recorded protocol change.

## Quick start

```bash
uv sync --all-extras
uv run bcqa --help
uv run bcqa manifest validate-all
uv run pytest

cd web
npm ci
npm run build
```

Run the deterministic local demonstration without installing third-party tools:

```bash
uv run bcqa --run-id demo audit cli fixtures/cli-tools/healthy-tool.yaml
uv run bcqa --run-id demo results normalize
```

Normalizing a run also rebuilds `results/global/check-results.json` and
`results/global/check-results.csv` from every immutable run. To rebuild those tables
without executing an audit:

```bash
uv run bcqa results rebuild-global
uv run bcqa report build
```

The first real pilot package is Cutadapt 5.2. Its reviewed manifest, functional FASTQ
fixture, normalized results, and evidence artifact manifest are committed. Static-analysis
checks report measurements such as finding counts and coverage; a `PASS` means the
measurement completed, not that the source had zero findings.

## Repository map

- `src/bioconda_audit/`: audit engine and `bcqa` CLI
- `schemas/`: versioned machine-readable contracts
- `config/`: frozen settings, exclusions, rubric, and tool versions
- `manifests/`: reviewed package and cohort inputs
- `results/`: normalized, publishable results (raw large evidence is external)
- `web/`: results explorer
- `instructions/agents/`: bounded curation and adjudication tasks
- `docs/`: protocol, limitations, data dictionary, and change log

## Status semantics

Every check uses one of `PASS`, `FAIL`, `PARTIAL`, `NOT_APPLICABLE`, `UNTESTABLE`, `ERROR`, or `NOT_RUN`. `ERROR` means the audit machinery failed and is never counted as a package failure.

## Licensing

Repository code is MIT licensed. Original documentation and generated audit datasets are intended for release under CC BY 4.0. Third-party sources retain their own licences and are referenced rather than redistributed.
