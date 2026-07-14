# Seebot

**Study title:** *Seebot: a reproducible audit of software-engineering practices in widely downloaded Bioconda tools*

Seebot is a code-first research project for selecting a frozen cohort of Bioconda packages, retrieving the exact packaged source, running conservative and reproducible checks, preserving evidence, and publishing analysis-ready results through a web application.

The project measures observable properties. It does not label software as “good” or “bad”, infer scientific validity from engineering signals, or collapse distinct domains into a single quality score.

## Current phase

Seebot is in the **10-package pilot** phase. The 200-package study must not start until the pilot is reproducible and its schemas, exclusion vocabulary, and rubric have been frozen through a recorded protocol change.

## Quick start

```bash
uv sync --all-extras
uv run seebot --help
uv run seebot manifest validate-all
uv run pytest

cd web
npm ci
npm test
npm run build
```

Run the deterministic local demonstration without installing third-party tools:

```bash
uv run seebot --run-id demo audit cli fixtures/cli-tools/healthy-tool.yaml
uv run seebot --run-id demo results normalize
```

Normalizing a run also rebuilds `results/global/check-results.json` and
`results/global/check-results.csv` from every immutable run. To rebuild those tables
without executing an audit:

```bash
uv run seebot results rebuild-global
uv run seebot report build
```

The three-package mini-pilot covers Cutadapt 5.2, NanoPlot 1.47.1, and sourmash
4.9.4. Each has a reviewed manifest, a small functional fixture, and normalized results.
Pixi installs the reviewed version and records the native solved artifact and lock hash.
This development runner does not claim to execute the frozen Linux package when running
on macOS. Raw pilot evidence remains local until persistent Cloudflare storage is added;
the public website currently publishes only normalized summaries.

Results also carry a `result_kind`. Contract checks use the normal outcome vocabulary;
successful observational checks are presented as `MEASURED`, because completing a
static-analysis measurement is not a claim that the software has no findings.

## Repository map

- `src/seebot/`: audit engine and `seebot` CLI
- `schemas/`: versioned machine-readable contracts
- `config/`: frozen settings, exclusions, rubric, and tool versions
- `manifests/`: reviewed package and cohort inputs
- `results/`: normalized, publishable results (raw large evidence is external)
- `web/`: results explorer
- `instructions/agents/`: bounded curation and adjudication tasks
- `docs/`: protocol, limitations, data dictionary, and change log

## Status semantics

Every check uses one of `PASS`, `FAIL`, `PARTIAL`, `NOT_APPLICABLE`, `UNTESTABLE`,
`ERROR`, or `NOT_RUN`. `ERROR` means the audit machinery failed and is never counted
as a package failure. The website renders a successful measurement as `MEASURED`
while preserving its machine status as `PASS`.

## Licensing

Repository code is MIT licensed. Original documentation and generated audit datasets are intended for release under CC BY 4.0. Third-party sources retain their own licences and are referenced rather than redistributed.
