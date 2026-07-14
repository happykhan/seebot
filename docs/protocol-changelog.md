# Protocol changelog

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
  contracts, source measurements, repository observations, recipe depth, and evidence.
