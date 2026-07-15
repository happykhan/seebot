# Data dictionary

## Project manifest

One YAML document separates project identity, repository snapshot, candidate-discovery
metadata, generic installation adapter, production-source roots, executable interfaces,
valid-run contract, robustness probes, and curation provenance.

## Observation

Every observation records project, snapshot, source component or executable interface,
check identifier, applicability, status, method, expected contract, observed facts,
command, tool identity, start time, duration, environment identity, configuration hash,
and evidence paths.

## Native finding

Analyzer findings retain analyzer name/version, native rule, native category/severity where
provided, repository-relative file and line, production-line denominator, and snapshot.
Rules from different analyzers are never silently merged.

## Exemplar view

Exemplar labels are deterministic derived facts, not scores. Code-health values do not
affect eligibility. `NOT_APPLICABLE` and `NOT_EXISTING` can be accepted for Complete
assessment; missing, errored, or untestable required evidence cannot.

## Public evidence

The website publishes normalized observations, commands with normalized paths, hashes,
tool versions, status details, and output inventories. Raw stdout/stderr remains in the
local evidence tree referenced by relative paths. The site does not publish complete
third-party repositories, source excerpts, large raw analyzer dumps, absolute local paths,
credentials, caches, or large generated outputs.
