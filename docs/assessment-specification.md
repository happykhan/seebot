# Revised assessment specification

This file records the frozen implementation decisions for the current assessment model.

## Product claim

Seebot is an observational dataset and explorer. It does not rank projects or combine
unrelated measurements into an overall score. Projects can receive factual Usage exemplar,
Repository-practice exemplar, Complete assessment, and Practice exemplar labels.

## Supported source languages

Python, Perl, C, C++, Rust, and Java receive language-specific profiles. Cython receives a
limited, separate structural profile. Primary-R projects are excluded from the initial
cohort. A materially unsupported production language prevents Complete assessment.

## Historical measurements

Use the default-branch commit at or before 1 July for 2021 through 2026. Historical years
through 2025 receive source-derived measurements only. Repository, dependency, CI, and
executable observations apply to the canonical 1 July 2026 snapshot.

## Source measurements

- production source lines and language composition;
- median, 90th percentile, and maximum file length;
- counts and percentages of files over 500 and 1,000 lines;
- median, 90th percentile, and maximum function length;
- functions over 50 and 100 lines;
- complexity distribution and counts over 10 and 20;
- maximum nesting and functions with more than five parameters;
- duplication percentage;
- native analyzer findings and native rules per 1,000 production lines;
- language-appropriate API documentation coverage;
- native security findings and current dependency advisories.

Tests are ignored entirely by code-health measurements. Build-dependent analyzers are
supplementary and never run upstream tests.

## Usage probes

All installed commands receive help/version discovery. A primary interface receives one
curated valid run and the seven mandatory invalid-input scenarios. Stream support is
observed with explicit applicability. Exact repeatability and whole-output hashes are not
metrics.

The valid run asserts zero exit, bounded execution, no crash, expected non-empty outputs,
parseable format, selected structural facts, and clean side effects. Slow or externally
dependent tools remain in repository/code analysis and receive a specific UNTESTABLE
reason for usage.

## Survey and fixtures

The metadata-first top-200 survey records repository mapping, primary language, executable
surface, input/output models, database needs, runtime class, and shared/bespoke fixture
needs. A coherent shared synthetic genomics fixture pack is created after the survey, with
stable malformed variants and documented tool-specific exceptions.

## Rerunnable harness

One YAML project manifest declares repository, snapshot, generic installation adapter,
source roots, executable interfaces, fixtures, probes, applicability, and curation. Shared
Python runners collect deterministic evidence. Users can select project, category,
language, check family, check, and historical year. Accepted manifests rerun without an
agent. Agents are limited to initial curation, ambiguity review, and adjudication.
