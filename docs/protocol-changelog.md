# Protocol changelog

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
