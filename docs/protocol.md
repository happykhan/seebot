# Seebot protocol

## Objective

Seebot is an evidence-based observatory for public scientific software. It records
repository practices, language-specific source measurements, and the behaviour of
installed command-line interfaces. It does not produce an aggregate quality score,
project ranking, or scientific-validity judgement.

The initial cohort is discovered from Bioconda download data because Pixi provides a
practical installation route. Bioconda packages and recipes are collection machinery,
not units of assessment and not project-health metrics.

## Units of analysis

The following identifiers are kept separate:

1. Project: the named software product.
2. Repository: the public GitHub owner and repository.
3. Repository snapshot: the exact default-branch commit at or before the cutoff date.
4. Source component: one supported language and its reviewed production roots.
5. Executable interface: one installed public command.
6. Installation record: the adapter and resolved artifact used to create the environment.
7. Audit run: the commands, fixtures, configurations, environment, and evidence.

## Scope and exclusions

Repository and source observations can apply to any eligible public GitHub project.
Usage observations apply only to installed command-line interfaces. The initial full
cohort contains end-user scientific CLI tools whose primary production language is
Python, Perl, C, C++, Rust, Java, or Cython. Cython has a deliberately limited structural
profile. Primary-R projects are excluded in this phase.

Exclusion decisions use the frozen codes in `config/exclusions.yaml`. Archived projects
remain in the dataset but cannot qualify as repository-practice exemplars.

## Cohort and snapshot policy

Rank package names using official Bioconda download records from 2025-07-01 through
2026-06-30, aggregated across versions, builds, variants, and platforms. Downloads are an
installation signal, not a count of users. Inspect enough ranked candidates to select the
first 200 eligible, de-duplicated upstream projects.

The canonical current snapshot is the default-branch commit at or immediately before
2026-07-01. Historical source-only snapshots use the commit at or before 1 July in 2021,
2022, 2023, 2024, and 2025. `NOT_EXISTING` records years before a repository existed.

Historical analysis is limited to source-derived measurements under one frozen analyzer
configuration. Current-only observations include repository practices, executable
behaviour, dependency advisories, CI state, and other external-state measurements.

## Survey and pilot gates

The 200-candidate interface and fixture survey must complete before the shared fixture
catalogue is frozen. The survey is metadata-first and does not install or execute every
candidate.

A newly selected ten-project pilot must then demonstrate:

- deterministic reruns from a clean checkout;
- schema validation for every manifest, fixture, observation, and normalized result;
- explicit applicability, exclusion, and untestable reasons;
- evidence preservation, overwrite, selection, and cleanup behaviour;
- independent review of all ten manifests;
- coverage of supported languages, common input types, and different output models;
- bounded disk, CPU, memory, network, and runtime behaviour.

The 200-project execution remains locked until the revised pilot is reproducible.

## Repository-practice observations

Seebot records activity and release recency as descriptive values. Only explicit GitHub
archived status affects exemplar eligibility. Standard tests are detected from recognized
files, framework declarations, and conventional patterns. Seebot never executes upstream
test suites. Verification CI requires a workflow that appears to build, check, lint, or
invoke a standard test runner; a release-only workflow is not verification CI.

## Source-analysis policy

Only reviewed production source is measured. Tests, generated code, vendored dependencies,
build output, minified files, documentation examples, fixtures, and data are excluded.
Included and excluded paths and denominators are published.

Analyzer findings retain their native rule codes and native categories. Values are
compared only when language, analyzer, configuration, and denominator are compatible.
Cross-tool synthetic finding categories are not created. Source measurements never affect
exemplar eligibility; only successful completion affects assessment coverage.

## Executable-behaviour policy

Every public executable receives lightweight help/version discovery. One declared primary
interface receives the full valid-input and robustness suite unless several interfaces are
clearly co-primary.

Commands run in a pinned Linux x86-64 environment with two virtual CPUs, 8 GB RAM, a 5 GB
per-tool workspace, bounded process count, and no network during probes. Discovery checks
have a 15-second limit, invalid-input checks 30 seconds, and a miniature valid run five
minutes. Resource exhaustion is `UNTESTABLE`, not project failure.

The mandatory invalid-input scenarios are missing input, zero-byte input, malformed input,
valid but wrong format, unrecognized option, invalid option value, and unwritable output
where applicable. Each records exit status, stdout, stderr, timeout, crash/traceback
markers, and created files. Tool-output repeatability and exact-output hashing are not
assessment metrics.

## Fixtures

Shared, version-controlled fixture identifiers cover common genomics formats and stable
malformed variants. Fixtures record hashes, provenance, format, validity, and intent.
Tool-specific fixtures are documented exceptions when the shared set cannot exercise a
meaningful path. Large or externally licensed data are never copied into the repository.

## Status policy

`PASS` and `FAIL` describe executable contracts only. Measurements use `OBSERVED` and
`NOT_OBSERVED`. `NOT_APPLICABLE`, `UNTESTABLE`, `ERROR`, `NOT_RUN`, and `NOT_EXISTING`
retain their literal meanings. Audit machinery failures are never reinterpreted as project
failures.

Public wording translates statuses into factual labels such as “Observed”, “Could not
assess”, “Handled gracefully”, and “Did not handle gracefully”.

## Exemplar labels

- **Usage exemplar:** every applicable required usage contract passes.
- **Repository-practice exemplar:** the repository is not archived and all required
  repository practices are observed.
- **Complete assessment:** every applicable current and historical measurement completes;
  `NOT_EXISTING` and justified `NOT_APPLICABLE` are accepted.
- **Practice exemplar:** all three preceding labels apply.

Code-health values never qualify or disqualify a project.

## Storage and reruns

Each observation records commands, versions, hashes, timestamps, environment identity,
duration, and evidence paths. Completed evidence is reused unless `--force` is supplied.
During this development phase a forced run overwrites the current generated result rather
than publishing parallel result versions.

Pixi uses a Seebot-specific cache. The default total Seebot storage budget is 20 GB and
the per-tool workspace limit is 5 GB. Tool environments and temporary checkouts are
removed after evidence is preserved. Cleanup never touches unrelated user caches.
