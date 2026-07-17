# Protocol changelog

## 2026-07-17 — compact beta evidence retention

- Designated normalized tables and the generated website dataset as the retained beta products.
- Allowed the complete per-check evidence tree, including `result.json`, raw analyzer streams,
  duplicate metadata, and fixture sandboxes, to be removed after validation, normalization,
  and website generation.
- Kept rerunning as the recovery path while the assessment and presentation are still changing;
  this does not alter the rubric, schemas, exclusions, or recorded project outcomes.
- Raised the bounded Python Slurm tasks to eight CPUs and 16 GiB and allowed Pylint to use
  eight workers. Execution resources remain beta machinery and do not affect project outcomes.
- Stopped running native lint, security, and dead-code analyzers on historical snapshots because
  the beta website presents those findings only for current source. Historical runs now collect
  the structural measurements used by the time-series charts.
- Parallelized connected preparation with a conservative four configurable workers for source
  snapshots and project Pixi environments; this changes preparation time, not outcomes and
  avoids swamping the shared head node.
- Removed all SHA-256 passes over staged Git snapshots, including their Git indexes. Preparation
  checks each checkout's commit with `git rev-parse HEAD` and hashes only smaller configuration
  and runtime inputs.
- Cached stable runtime and audit-code identities per worker so result rows no longer repeatedly
  hash the Pixi executable or launch duplicate Git identity commands. Array verification checks
  that Pixi is executable instead of hashing the same binary in every task.

## 2026-07-16 — semantically empty input contract

- Added a separate usage-health contract for format-valid inputs containing zero biological
  records, including empty FASTA, FASTQ and PAF streams and header-only SAM and VCF.
- Kept the existing zero-byte error-handling probe separate. The new contract requires
  successful execution, no internal crash, structurally valid output, and a verified output
  record count of zero where the operation has a meaningful empty result.
- Extended output evidence with parsed record cardinality and added explicit
  `NOT_APPLICABLE` and `NOT_RUN` handling when an operation has no meaningful empty result or
  still requires format-specific curation.
- Updated the frozen rubric, schema, fixtures, curation generators, public catalogue and
  regression tests. This amendment does not authorize execution of the broader cohort.

## 2026-07-16 — bounded Python expansion authorised

- Authorised a bounded expansion of 20 Python-primary command-line projects from the
  ranked candidate survey; this does not unlock the remaining 200-project cohort.
- Selected the next ranked candidates after source-level interface review. `dnaio` was
  not promoted because its upstream project is a library without a declared end-user
  command; IGV Reports was selected as the next confirmed Python CLI.
- Added pinned current and historical source commits, exact package artifacts, reviewed
  production-source roots, interface contracts, and two review records per project.
- Added small reusable fixtures for Snakemake and Cooler. Upstream test suites remain
  prohibited. Full execution and publication wait for the reproducible x86-64 audit run.

## 2026-07-16 — ecosystem-specific dependency advisory coverage

- Retained OSV-Scanner for its supported ecosystem manifests and lockfiles, rather than
  treating it as a C/C++-specific analyzer.
- Added CPAN Audit 20260622.001 for Perl projects that declare dependencies in `cpanfile`
  or `cpanfile.snapshot`.
- Added an installed-environment observation that inventories the exact Pixi dependency
  closure and checks packages exposing exact PyPI, Maven, or npm identities.
- Added PEP 621 and dependency-group parsing for Python `pyproject.toml`, preserving
  runtime, optional, build, and development roles without treating declarations as
  resolved versions.
- Separated runtime dependency inputs from files found only under documentation, test,
  example, or benchmark paths. A zero-advisory result is published only when a supported
  runtime dependency input or exact installed ecosystem package was scanned. Conda-only
  inventories are reported separately.
- Added repository, source, usage, and dependency as the four consistent public reporting
  areas. The frozen rubric, source exclusions, and broader-run gate are unchanged.

## 2026-07-15 — assessment model v2 frozen

- Replaced the package/recipe-oriented model with upstream project, repository snapshot,
  production source component, executable interface, and installation identifiers.
- Completed the metadata-first survey of 1,000 download-ranked discovery candidates. It
  found 272 explicit eligible CLIs; the first 200 were reached at rank 816.
- Selected and double-reviewed a fresh ten-project reproducibility cohort spanning Python,
  Cython, Perl, C, C++, Rust, and Java. Primary-R projects remain excluded; Cython uses a
  limited profile rather than being excluded.
- Froze the current snapshot at 1 July 2026 and source-only snapshots at 1 July 2021–2025.
  Repository, dependency, and executable observations are current only.
- Froze production-source exclusions: all test source, generated and vendored code, build
  output, documentation, examples, fixtures, and data are outside code-health denominators.
- Froze native analyzer identities and rule codes. Cross-language synthetic finding
  categories and aggregate quality scores are prohibited.
- Added one curated valid run, stdin/stdout observation where applicable, and seven bounded
  invalid-input scenarios. Resource exhaustion is `UNTESTABLE`; audit machinery failure is
  `ERROR`; neither is converted to project failure.
- Confirmed that Seebot detects standard upstream tests and verification CI but never runs
  upstream test suites.
- Replaced temporary public progress language and placeholder metrics with current project
  reports, compatible aggregate distributions, native-rule tables, robustness outcomes,
  language use, repository practices, and source history.
- Kept the broader 200-project execution locked. Freeze completion does not authorize or
  trigger that run.

## 2026-07-15 — first Rust-only pilot package (pilot, unfrozen)

- Added Rasusa 4.1.0 as the fourth completed pilot package, pinned to the shared
  Bioconda recipe snapshot and exact Linux package artifact.
- Added a reviewed seeded subsampling test over a synthetic six-read FASTQ fixture;
  two independent runs produced the same frozen output hash.
- Adopted `@genomicx/ui` for shared navigation, theme controls, and design tokens on
  the public results site without changing the rubric or award definition.

## 2026-07-15 — literature-backed rubric and dedicated reports (pilot, unfrozen)

- Replaced weak convenience metrics with testing, documentation/usability,
  reproducibility/releases, automation/maintenance, and reuse/attribution domains.
- Added assessment coverage; unknown audit evidence no longer masquerades as failure.
- Added executable checks for substantive help output, clean diagnostics, filesystem
  side effects, and repeatable interface behaviour.
- Split the overview, project directory, and tool reports into dedicated routes, with
  report views for summary, upstream practices, testing, code health, behaviour, and methods.

## 2026-07-15 — upstream-focused public report (pilot, unfrozen)

- Removed the public comparison interface and recipe-test presentation.
- Replaced the award formula with five upstream-project categories: testing,
  automation, documentation, stewardship, and reproducibility.
- Added conservative repository-tree observations for test files and data, CI and
  maintenance automation, project guidance, dependency manifests, lock files,
  containers, source-language counts, and worked examples.
- Kept source static analysis and installed-tool behaviour visible but outside the
  upstream award.

## Earlier unfrozen development

- Established the original project naming, separated units of analysis, conservative status semantics, ten-package pilot gate, and first CLI-help rubric item.
- Renamed the project to Seebot during the unfrozen pilot phase.
- Introduced `CONTRACT` and `MEASUREMENT` result kinds. Successful measurements are
  displayed as `MEASURED` and are not counted as software passes.
- Adopted a Pixi-first native development runner that records the solved package,
  platform, package URL and hash, and lockfile hash. Native runs are not represented
  as execution of a different frozen Linux artifact.
- Added Cutadapt 5.2, NanoPlot 1.47.1, and sourmash 4.9.4 as the three-package
  mini-pilot. Each has a reviewed miniature functional test with hash-checked output.
- Expanded the active pilot with Rasusa 4.1.0 as the first standalone Rust package;
  its seeded miniature FASTQ subsampling test has hash-checked output.
- Added conservative recipe-test source suggestions and explicit mismatch evidence;
  the reviewed component facts remain authoritative pending rendered-recipe support.
- Replaced the pass-count landing page with package profiles that separate executable
  contracts, source measurements, repository observations, recipe depth, and execution
  provenance.
- Removed temporary GitHub Release evidence publishing. The mini-pilot website exposes
  normalized summaries only; raw evidence will move to Cloudflare storage later.
- Added the versioned Seebot Engineering Practice Award, competition ranking, generated
  SVG badges, cohort metric aggregation, and a searchable/paginated tool directory. The
  award excludes static-analysis counts and makes its limited scope explicit.
