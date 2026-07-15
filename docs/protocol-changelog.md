# Protocol changelog

## 2026-07-15 — upstream-focused public report (pilot, unfrozen)

- Removed the public comparison interface and recipe-test presentation.
- Replaced the award formula with five upstream-project categories: testing,
  automation, documentation, stewardship, and reproducibility.
- Added conservative repository-tree observations for test files and data, CI and
  maintenance automation, project guidance, dependency manifests, lock files,
  containers, source-language counts, and worked examples.
- Kept source static analysis and installed-tool behaviour visible but outside the
  upstream award.

## Unreleased pilot

- Established the original project naming, separated units of analysis, conservative status semantics, ten-package pilot gate, and first CLI-help rubric item.
- Renamed the project to Seebot during the unfrozen pilot phase.
- Introduced `CONTRACT` and `MEASUREMENT` result kinds. Successful measurements are
  displayed as `MEASURED` and are not counted as software passes.
- Adopted a Pixi-first native development runner that records the solved package,
  platform, package URL and hash, and lockfile hash. Native runs are not represented
  as execution of a different frozen Linux artifact.
- Added Cutadapt 5.2, NanoPlot 1.47.1, and sourmash 4.9.4 as the three-package
  mini-pilot. Each has a reviewed miniature functional test with hash-checked output.
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
