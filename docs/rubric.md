# Rubric

The canonical machine-readable rubric is `config/rubric.yaml`. Stable check identifiers preserve comparability when wording changes.

Domains are reported separately: cohort, package, recipe, repository, source, Python
analysis, CLI behaviour, robustness, reproducibility, security indicators, and manual
review.

The dashboard additionally calculates the versioned **Seebot Engineering Practice
Award** defined in `config/awards.yaml`. This is not a general software-quality or
scientific-validity score. Its 100 transparent points are limited to:

- 50 points for five independently observed executable contracts;
- 30 points for six repository-practice signals;
- 20 points for reviewed Bioconda recipe-test depth.

Gold begins at 85 points, silver at 70, and bronze at 55. Ties retain the same competition
rank. Missing or errored scored checks make a package ineligible rather than silently
awarding zero. Static-analysis counts are excluded from the award because treating tool
findings as penalties would turn observations into unsupported quality judgements.

Automated observations are not judgements. A linter finding is not necessarily a bug; a test directory does not establish test effectiveness; a CI file does not establish a passing build; absence of a detected vulnerability does not prove security.
