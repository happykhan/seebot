# Cohort

Seebot ranked Bioconda package names using official download records from 2025-07-01 through
2026-06-30, aggregated across versions, builds, variants, and platforms. Inspect at least
300 candidates and preserve every rank and exclusion reason.

The initial target is the first 200 eligible, de-duplicated public GitHub projects that
provide an end-user command-line interface and use a supported primary production
language. Primary-R projects are excluded in this phase. Popularity selects candidates but
is never a health metric.

The completed metadata-first survey contains 1,000 ranked package names. It found 272
de-duplicated projects with explicit eligible end-user CLI evidence; the 200th eligible
project was reached at rank 816. The survey records repository mapping, executable
surface, primary language, project category, input/output formats, reference-data needs,
runtime class, and likely shared or bespoke fixture requirements.

The ten-project reproducibility cohort was selected from the first 200 eligible projects to
cover every supported language profile, common genomics formats, file and stream interfaces,
and different output models. Each manifest has two recorded review passes. The cohort is
SAMtools, BCFtools, FastTree, Cutadapt, fastp, FAMSA, yacrd, Pyrodigal, MinCED, and
any2fasta.

The broader 200-project execution remains intentionally locked. The ten current reports
are the published assessment dataset; the remaining survey rows are discovery evidence,
not partial project reports.

A bounded 20-project Python expansion was authorised on 16 July 2026. The selected
projects are Harpy, deepTools, HTSeq, Snakemake, the DNAnexus toolkit, ProPhyle, pyfaidx,
SEPP, ANARCI, MetaPhlAn, DendroPy, SAMsift, PASTA, CRISPRme, ITSxpress, scanpy-scripts,
zDB, Cooler, RGI, and IGV Reports. Their manifests and two review passes are curated, but
they do not become public reports until the complete x86-64 audit is collected and
validated. This bounded expansion does not authorise execution of the rest of the ranked
cohort.
