# Data dictionary

## Identifiers

- `package_id`: `{name}__{version}__{build}__{subdir}` for an exact Bioconda artifact.
- `upstream_project_id`: stable curated identifier grouping aliases or split packages.
- `run_id`: operator-supplied immutable audit execution identifier.
- `check_id`: stable rubric identifier.
- `environment_id`: content-derived identifier for the execution environment.
- `config_sha256`: SHA-256 of the effective audit configuration.

## States

- `PASS`: observed result satisfies the declared expectation.
- `FAIL`: observed result does not satisfy the expectation.
- `PARTIAL`: expectation has independently meaningful satisfied and unsatisfied components.
- `NOT_APPLICABLE`: check does not apply to this package/interface.
- `UNTESTABLE`: applicable in principle but cannot be tested under the frozen protocol.
- `ERROR`: audit machinery failed; excluded from failure counts.
- `NOT_RUN`: deliberately or not yet executed.

