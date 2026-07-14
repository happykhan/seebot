# Three-package mini-pilot acceptance

The mini-pilot exists to expose protocol and implementation problems before the
ten-package pilot. It does not unlock the 200-package study.

## Scope

The provisional package set is Cutadapt, NanoPlot, and sourmash. Each must be a
reviewed end-user Python CLI with a miniature functional test.

## Acceptance criteria

- The default development runner installs the reviewed package version with Pixi.
- Every Pixi run records its lock hash, native platform, and exact solved package build.
- A native development run is never represented as execution of a different frozen
  Linux artifact.
- CLI help, version, invalid-option, and functional probes preserve raw evidence.
- Measurement-only checks are displayed as `MEASURED`, not as package `PASS` outcomes.
- Contract outcomes, measurements, audit errors, and applicability states remain
  visibly distinct.
- Each package has a useful results profile rather than only raw check rows.
- The website publishes normalized summaries only. Raw evidence remains local during
  this mini-pilot until the planned Cloudflare storage layer is implemented.
- Core Pixi execution, normalization, status presentation, and web loading have tests.
- All three packages rerun from a clean checkout before the mini-pilot is declared
  complete.

## Gate

The rubric remains unfrozen. Findings from this mini-pilot may change schemas and
wording. The ten-package pilot begins only after these criteria are satisfied and the
changes are recorded in the protocol changelog.
