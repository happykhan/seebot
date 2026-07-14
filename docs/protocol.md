# SeeBot protocol

## Objective

SeeBot audits observable software-engineering practices in widely downloaded Bioconda tools. It links frozen download data, an exact Bioconda package build and recipe, the recipe's verified source release, an upstream repository snapshot, executable-level black-box probes, and normalized evidence-backed results.

Scientific algorithm validation is outside version 1 and requires later tool-class-specific protocols.

## Units of analysis

The following identifiers are never conflated:

1. Bioconda package: channel name, version, build, subdirectory, URL, and checksum.
2. Packaged release source: the archive or commit named by the pinned recipe.
3. Upstream repository: live project metadata observed on the audit date.
4. Executable interface: one or more commands exposed by a package.
5. Upstream project: the software product to which package aliases may map.

Release-source metrics use verified recipe source. Current repository-practice checks use the upstream commit recorded at audit time.

## Pilot gate

The first cohort contains ten deliberately varied packages. Before expanding to 200 packages, maintainers must demonstrate:

- deterministic reruns from a clean checkout;
- schema validation for every manifest, review, and result;
- explicit handling of exclusions and ambiguous states;
- evidence preservation and resume behaviour;
- inter-reviewer adjudication for agent tasks;
- a frozen rubric and protocol version.

## Status policy

`PASS`, `FAIL`, and `PARTIAL` describe a check's observed outcome against its declared expectation. `NOT_APPLICABLE`, `UNTESTABLE`, and `NOT_RUN` describe scope or execution decisions. `ERROR` describes audit machinery failure and is excluded from package-failure denominators.

## Cohort policy

Rank package names by downloads across versions, builds, variants, and supported platforms in twelve complete calendar months from the official Anaconda package-download dataset, filtered to `data_source == "bioconda"`. Inspect at least 300 candidates and curate 200 eligible end-user tools. If the requested final month is incomplete, shift the window backwards and record the actual period.

Downloads are a package-installation signal and may include dependency resolution, automation, CI, and repeated installation. Reports say “most downloaded packages”, not “most used software”.

## Execution policy

Commands run without network access unless the manifest explicitly declares it, with a fixed timeout and isolated working directory. A result records the exact command, environment identity, configuration hash, start time, duration, exit code or signal, and stdout/stderr paths. Resume never replaces completed evidence unless `--force` is supplied.

## Result aggregation

Normalization updates an append-only global fact table with one row per package, run, and
rubric check. The web application reads the lossless JSON form; statistical workflows may
read the CSV export. The table preserves every explicit state, including `ERROR` and
`UNTESTABLE`, and never collapses domains into a composite quality score.
