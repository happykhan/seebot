# Seebot

Seebot is an evidence-based observatory for scientific software. It records public GitHub
repository practices, language-specific production-source measurements, and the behaviour
of installed command-line interfaces.

Seebot does **not** produce an overall quality score, ranking, medal, or scientific-validity
judgement. It can apply factual labels when evidence is complete:

- Usage exemplar
- Repository-practice exemplar
- Complete assessment
- Practice exemplar

## Current development state

The assessment model is being rebuilt from an earlier package-oriented pilot. The revised
workflow is gated:

1. Survey the 200 most-downloaded eligible Bioconda-discovered candidates without bulk
   installation.
2. Freeze the project categories and shared fixture catalogue.
3. Select and independently review a new ten-project pilot.
4. Demonstrate clean, deterministic reruns of the pilot.
5. Only then unlock the 200-project execution.

Bioconda downloads provide candidate discovery and Pixi provides the first installation
adapter. Neither Bioconda recipes nor package metadata are project-health metrics.

## Commands

Install the development environment:

```bash
make install
```

Validate project manifests and shared fixtures:

```bash
make schemas
```

List or export the metadata-first interface survey:

```bash
uv run seebot survey list
uv run seebot survey list --language rust
uv run seebot survey export
```

Plan selectable current and historical work without execution:

```bash
uv run seebot audit plan --tool cutadapt --check usage --check robustness
uv run seebot history plan --tool cutadapt --year 2023
```

Inspect and safely prune only Seebot-owned cache/work directories:

```bash
uv run seebot cache status
uv run seebot cache prune --yes
```

Run all repository checks:

```bash
make check
```

## Assessment sections

### Repository health

Activity and release recency, verification CI, recognized standard test patterns,
documentation, installation and usage instructions, licence, citation, and contribution
infrastructure. Upstream tests are never executed.

### Code health

Production source only: language composition, source and file sizes, function structure,
complexity, duplication, documentation coverage, native linter findings, native security
indicators, and current dependency advisories. Tests, generated code, vendored code,
fixtures, documentation, and data are excluded from denominators.

### Usage and robustness

Help/version discovery, one curated miniature valid run, stream behaviour where applicable,
and seven invalid-input scenarios. Probes run with bounded resources and no network.

## Key documentation

- [Protocol](docs/protocol.md)
- [Assessment catalogue](docs/rubric.md)
- [Agreed implementation specification](docs/assessment-specification.md)
- [Limitations](docs/limitations.md)
- [Cohort policy](docs/cohort.md)
