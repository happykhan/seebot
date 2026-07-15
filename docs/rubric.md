# Rubric

The canonical machine-readable rubric is `config/rubric.yaml`. Stable check identifiers preserve comparability when wording changes.

Domains are reported separately: cohort, package, recipe, repository, source, Python,
Perl, C/C++, Rust, CLI behaviour, robustness, reproducibility, security indicators, and
manual review.

Shared source concepts are parseability/buildability, normalized static findings,
complexity, documentation, duplication, dead-code indicators, security indicators, and
test execution. Language adapters retain their own semantics and within-language
baselines.

The dashboard additionally calculates the versioned **Seebot Engineering
Practice Award** defined in `config/awards.yaml`. This is not a general software-quality
or scientific-validity score. Its 100 literature-informed points are limited to:

- 30 points for testing and independent functional verification;
- 25 points for documentation and command-line usability;
- 20 points for reproducibility and identifiable releases;
- 15 points for automation and maintenance;
- 10 points for reuse and attribution.

Gold begins at 85 points, silver at 70, and bronze at 55. Ties retain the same competition
rank. Assessment coverage is published with every score. Unknown, errored, or untestable
evidence reduces coverage rather than silently becoming zero; coverage below 80% makes
the award ineligible. `NOT_APPLICABLE` evidence is excluded from its denominator.
Static-analysis counts remain outside the award.

Package size, installation duration, dependency count, lockfiles, containers, dependency
bots, issue templates, and code-of-conduct files do not earn points. They are mechanisms
or contextual facts, not general evidence of software quality.

Automated observations are not judgements. A linter finding is not necessarily a bug; a test directory does not establish test effectiveness; a CI file does not establish a passing build; absence of a detected vulnerability does not prove security.
