# Rubric

The canonical machine-readable rubric is `config/rubric.yaml`. Stable check identifiers preserve comparability when wording changes.

Domains are reported separately: cohort, package, recipe, repository, source, Python,
Perl, C/C++, Rust, CLI behaviour, robustness, reproducibility, security indicators, and
manual review.

Shared source concepts are parseability/buildability, normalized static findings,
complexity, documentation, duplication, dead-code indicators, security indicators, and
test execution. Language adapters retain their own semantics and within-language
baselines.

The dashboard additionally calculates the versioned **Seebot Upstream Engineering
Practice Award** defined in `config/awards.yaml`. This is not a general software-quality
or scientific-validity score. Its 100 transparent points are limited to:

- 25 points for upstream test-suite, test-configuration, and test-data signals;
- 20 points for CI, dependency-update, and release automation;
- 20 points for README, documentation-tree, and example signals;
- 20 points for licensing, contribution, conduct, citation, issue, and changelog files;
- 15 points for dependency manifests, lock files, and container or development setup.

Gold begins at 85 points, silver at 70, and bronze at 55. Ties retain the same competition
rank. A missing or errored repository observation makes a package ineligible rather than
silently awarding zero. Static-analysis counts and installed-tool behaviour are excluded
from the award because combining them into one number would overstate their semantics.

Automated observations are not judgements. A linter finding is not necessarily a bug; a test directory does not establish test effectiveness; a CI file does not establish a passing build; absence of a detected vulnerability does not prove security.
