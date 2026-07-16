# Assessment catalogue

The canonical machine-readable catalogue is `config/rubric.yaml`. Checks record
observations and executable contracts; they do not award points.

## Repository health

- archived status;
- days since the last non-bot commit;
- commits and active months in the preceding 12 months;
- latest release date and releases in the preceding 24 months;
- README, installation instructions, usage example, licence, and citation information;
- recognized standard test patterns and test-file count;
- verification CI and descriptive current CI state;
- optional documentation, changelog, contribution, security, issue-template, release, and
  dependency-automation observations.

Repository-practice exemplar requires a non-archived repository, README, licence, citation
instructions, recognized standard tests, verification CI, installation instructions, and
at least one usage example.

## Source health

Core source-derived measurements are production source lines, language composition,
file-length distribution, function-length distribution, cyclomatic-complexity distribution,
nesting, parameter counts, duplication percentage, native linter findings, documentation
coverage, and native source-security findings.

Dead-code candidates, unsafe-code occurrences, and build-dependent analyzers are
supplementary. Formatting compliance is not a code-health metric. No SOLID score or other
aggregate code-quality grade is produced.

Counts are normalized by an appropriate published denominator such as production kLOC or
recognized functions. Tests, generated code, vendored code, fixtures, documentation, and
data never enter production-code denominators.

## Dependencies

The current repository is inspected for supported dependency manifests and lockfiles.
Python `pyproject.toml` declarations are recorded by role, including runtime, optional,
build, and development requirements. The exact disposable Pixi installation is also
inventoried: its resolved Conda closure is retained, while exact PyPI, Maven, and npm
package versions are checked for known advisories. CPAN declarations use CPAN Audit.

Runtime advisory counts are published only when a supported runtime input was checked.
Unmapped installed packages remain visible as inventory rather than being reported as a
zero-advisory scan.

## Usage and robustness

Required interface contracts cover help, version identity, invalid-option rejection,
stderr diagnostics, bounded execution, absence of internal tracebacks/panics, and clean
side effects. Stream support is recorded but is required only when applicable to the
documented interface.

A curated miniature run demonstrates only that valid input is accepted and structurally
valid output is produced within the resource budget. It does not validate scientific
correctness. Seven mandatory malformed-input scenarios assess graceful behaviour.

## Aggregate exploration

The website exposes language trends, activity, long-file and long-function distributions,
complexity, duplication, documentation coverage, native linter-rule frequencies, native
security findings, repository-practice prevalence, and robustness outcomes. Analyzer data
are comparable only within compatible language/analyzer/configuration groups.

Groups smaller than ten show individual points. Groups of 10–19 show boxes plus points;
groups of at least 20 may show violins, boxes, and points. Underlying project points remain
visible. AI-tooling milestones are optional contextual annotations and never causal claims.
