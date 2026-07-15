# Cohort

Rank Bioconda package names using official download records from 2025-07-01 through
2026-06-30, aggregated across versions, builds, variants, and platforms. Inspect at least
300 candidates and preserve every rank and exclusion reason.

The initial target is the first 200 eligible, de-duplicated public GitHub projects that
provide an end-user command-line interface and use a supported primary production
language. Primary-R projects are excluded in this phase. Popularity selects candidates but
is never a health metric.

Before installation, the metadata-first survey records repository mapping, executable
surface, primary language, project category, input/output formats, reference-data needs,
runtime class, and likely shared or bespoke fixture requirements.

The new ten-project pilot is selected from that survey to cover supported languages,
common input types, and different interface/output patterns. The 200-project execution is
locked until all ten pilot projects rerun reproducibly from a clean checkout.
