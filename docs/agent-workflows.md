# Agent workflows

Agents perform bounded tasks defined in `instructions/agents/`. Each task receives one package manifest, relevant evidence, a schema, and an explicit output path. Agents must not run unrestricted audits, change rubric semantics, or overwrite script-generated facts.

Suggested automated mappings require confirmation. Ambiguous cases are escalated to an adjudicator. Agent outputs are validated exactly like other data and retain reviewer identity, round, confidence, source commit, and evidence notes.

