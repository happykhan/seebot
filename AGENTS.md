# Agent operating rules

This repository uses agents only for bounded curation and adjudication. Scripts remain the source of truth for deterministic collection, execution, normalization, and validation.

1. Read `docs/protocol.md`, `docs/rubric.md`, and the relevant file in `instructions/agents/` before changing data.
2. Never start the 200-package run until the 10-package pilot is reproducible and the rubric, schemas, and exclusions are frozen.
3. Never guess a value. Use explicit `UNKNOWN`, `NOT_APPLICABLE`, `UNTESTABLE`, `ERROR`, or `NOT_RUN` values as defined by the schema.
4. Do not reinterpret an audit command failure as a package failure. Machinery failures are `ERROR`.
5. Keep package, packaged release source, upstream repository, executable interface, and upstream project identifiers separate.
6. Store observations, not character judgements. Do not create an aggregate quality score.
7. Preserve evidence paths, hashes, commands, versions, timestamps, and environment identifiers.
8. Do not commit complete third-party repositories, large raw datasets, credentials, or copied source excerpts.
9. Changes to `config/rubric.yaml`, schemas, or exclusions after pilot freeze require a dedicated pull request and an entry in `docs/protocol-changelog.md`.
10. Run `make check` before handoff.

