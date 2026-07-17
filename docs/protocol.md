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

Historical analysis is limited to the structural source measurements displayed by the website:
inventory, file and function lengths, complexity, duplication, and documentation coverage.
Native lint, security, and dead-code analyzers are current-only, alongside repository practices,
executable behaviour, dependency advisories, CI state, and other external-state measurements.

## Survey and reproducibility gates

The 200-candidate interface and fixture survey must complete before the shared fixture
catalogue is frozen. The survey is metadata-first and does not install or execute every
candidate.

The newly selected ten-project reproducibility cohort must demonstrate:

- deterministic reruns from a clean checkout;
- schema validation for every manifest, fixture, observation, and normalized result;
- explicit applicability, exclusion, and untestable reasons;
- evidence preservation, overwrite, selection, and cleanup behaviour;
- independent review of all ten manifests;
- coverage of supported languages, common input types, and different output models;
- bounded disk, CPU, memory, network, and runtime behaviour.

The survey and ten-project gate are complete and the rubric, schemas, exclusions, fixture
catalogue, and analyzer versions are frozen. The 200-project execution remains locked until
it is separately authorized; completing this gate does not trigger a bulk run.

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

## Dependency-advisory policy

Current dependency evidence combines two observations. The repository observation scans
supported manifests and lockfiles and records Python dependency declarations from
`pyproject.toml` as runtime, optional, build, or development requirements. The installed
observation inventories the exact dependency closure in the disposable Pixi environment.

Installed packages are submitted for advisory lookup only when their exact name, version,
and ecosystem can be recovered from PyPI distribution metadata, Maven JAR metadata, or npm
package metadata. CPAN declarations are checked with CPAN Audit. Every resolved Conda
package remains in the installation inventory, including native libraries for which there
is no sound OSV ecosystem mapping. A zero-advisory result requires at least one supported
runtime source or exact installed ecosystem package; an inventory without such a mapping
is reported as inventory-only.

## Executable-behaviour policy

Every public executable receives lightweight help/version discovery. One declared primary
interface receives the full valid-input and robustness suite unless several interfaces are
clearly co-primary.

Commands run in a pinned Linux x86-64 environment with bounded process count, workspace, and
no network during probes. During beta HPC tuning, a project task may use eight CPUs and 16 GB
RAM; these execution resources are machinery rather than project-quality criteria. Discovery
checks have a 15-second limit, invalid-input checks 30 seconds, and a miniature valid run five
minutes. Resource exhaustion is `UNTESTABLE`, not project failure.

The mandatory robustness scenarios are missing input, zero-byte input, semantically empty
input, malformed input, valid but wrong format, unrecognized option, invalid option value,
and unwritable output where applicable. Semantically empty inputs are valid instances of
their declared format containing zero biological records, such as an empty FASTQ stream or
a header-only SAM or VCF. This check requires successful execution and structurally valid
output representing zero records; it is separate from graceful rejection of unusable
zero-byte input. Each probe records exit status, stdout, stderr, timeout, crash/traceback
markers, created files, output structure, and record cardinality where defined. Tool-output
repeatability and exact-output hashing are not assessment metrics.

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

During beta development, normalized result tables and the generated website dataset are the
retained products. The complete per-check evidence tree—including `result.json`, raw analyzer
output, duplicate metadata, and fixture sandboxes—may be removed after validation,
normalization, and website generation. A compacted run is regenerated by rerunning it; beta
releases do not promise a permanent raw evidence archive. Before compaction, completed result
records are reused unless `--force` is supplied. A forced run overwrites the current generated
result rather than publishing parallel result versions.

Pixi uses a Seebot-specific cache. The default total Seebot storage budget is 20 GB and
the per-tool workspace limit is 5 GB. Tool environments and temporary checkouts are
removed after evidence is preserved. Cleanup never touches unrelated user caches.
