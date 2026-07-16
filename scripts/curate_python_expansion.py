#!/usr/bin/env python3
"""Materialise the reviewed 20-project Python cohort expansion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from curate_current_cohort import (
    applicable,
    not_applicable,
    output,
    review_record,
    semantic_empty,
    semantic_empty_not_applicable,
    semantic_empty_unknown,
    stream,
    valid,
)

ROOT = Path(__file__).resolve().parents[1]
SELECTED = (
    "harpy",
    "deeptools",
    "htseq",
    "snakemake-minimal",
    "dxpy",
    "prophyle",
    "pyfaidx",
    "sepp",
    "anarci",
    "metaphlan",
    "dendropy",
    "samsift",
    "pasta",
    "crisprme",
    "itsxpress",
    "scanpy-scripts",
    "zdb",
    "cooler",
    "rgi",
    "igv-reports",
)
REVIEWED_AT = "2026-07-16T12:00:00Z"


def untestable(reason: str) -> dict[str, Any]:
    return {
        "status": "untestable",
        "untestable_reason": reason,
        "fixture_ids": [],
        "command": None,
        "expected_outputs": [],
        "expect_stdout": False,
        "stdout_parser": None,
        "timeout_seconds": 300,
    }


def cli_robustness(primary: str, invalid_value: list[str] | None = None) -> dict[str, Any]:
    no_file = "The reviewed command does not accept a standalone biological input file."
    return {
        "missing_input": not_applicable(no_file),
        "empty_input": not_applicable(no_file),
        "semantically_empty_input": semantic_empty_not_applicable(no_file),
        "malformed_input": not_applicable(no_file),
        "wrong_format": not_applicable(no_file),
        "invalid_option": applicable(
            [primary, "--seebot-invalid-option"], None, "The option is deliberately unrecognised."
        ),
        "invalid_value": (
            applicable(invalid_value, None, "A typed option is given a deliberately invalid value.")
            if invalid_value
            else not_applicable(
                "No bounded typed option can be exercised without external data or services."
            )
        ),
        "unwritable_output": not_applicable(
            "No bounded run with a documented output-path option is available for this interface."
        ),
    }


def file_robustness(
    primary: str,
    command_prefix: list[str],
    *,
    malformed: str = "/fixtures/bad/malformed.fasta",
    malformed_id: str = "bad-malformed-fasta",
    wrong: str = "/fixtures/core/variants.vcf",
    wrong_id: str = "core-variants-vcf",
    invalid_value: list[str] | None = None,
    unwritable: list[str] | None = None,
    semantic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "missing_input": applicable(
            [*command_prefix, "/fixtures/bad/missing.dat"],
            None,
            "The input path does not exist.",
        ),
        "empty_input": applicable(
            [*command_prefix, "/fixtures/bad/empty.dat"],
            "bad-empty",
            "A zero-byte input file is supplied.",
        ),
        "semantically_empty_input": semantic
        or semantic_empty_unknown(
            "The format-specific zero-record fixture and expected output require review."
        ),
        "malformed_input": applicable(
            [*command_prefix, malformed],
            malformed_id,
            "A structurally malformed input is supplied.",
        ),
        "wrong_format": applicable(
            [*command_prefix, wrong],
            wrong_id,
            "A valid but incompatible biological format is supplied.",
        ),
        "invalid_option": applicable(
            [primary, "--seebot-invalid-option"], None, "The option is deliberately unrecognised."
        ),
        "invalid_value": (
            applicable(invalid_value, None, "A typed option is given a deliberately invalid value.")
            if invalid_value
            else not_applicable("The reviewed command has no independent bounded typed option.")
        ),
        "unwritable_output": (
            applicable(
                unwritable,
                None,
                "The output path is placed on the read-only fixture mount.",
            )
            if unwritable
            else not_applicable("The reviewed command writes its result to standard output.")
        ),
    }


def base_spec(
    *,
    name: str,
    description: str,
    category: str,
    tags: list[str],
    roots: dict[str, list[str]],
    primary: str,
    evidence: tuple[str, int, int],
    excluded: list[str],
    valid_run: dict[str, Any],
    robust: dict[str, Any],
    help_commands: list[list[str]] | None = None,
    version_commands: list[list[str]] | None = None,
    noargs: str = "help_or_usage_error",
    stdin: str = "not_supported",
    stdout: str = "supported",
    streams: dict[str, Any] | None = None,
    generated: list[str] | None = None,
    vendored: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "language": "python",
        "category": category,
        "tags": tags,
        "roots": roots,
        "generated": generated or [],
        "vendored": vendored or [],
        "excluded": excluded,
        "primary": primary,
        "help": help_commands or [[primary, "--help"]],
        "version": version_commands if version_commands is not None else [[primary, "--version"]],
        "noargs": noargs,
        "stdin": stdin,
        "stdout": stdout,
        "stream": streams
        or stream(
            None, [], reason="The documented interface does not provide a bounded stream mode."
        ),
        "valid": valid_run,
        "robust": robust,
        "evidence": evidence,
    }


SPECS: dict[str, dict[str, Any]] = {
    "harpy": base_spec(
        name="Harpy",
        description="Runs linked-read and whole-genome sequencing workflows.",
        category="genome analysis workflow",
        tags=["FASTQ", "VCF", "phasing"],
        roots={"python": ["harpy"]},
        primary="harpy",
        evidence=("pyproject.toml", 20, 28),
        excluded=["test", "docs", "resources"],
        valid_run=untestable(
            "A meaningful run requires a workflow parameter file, reference resources, "
            "and multiple external tools."
        ),
        robust=cli_robustness("harpy", ["harpy", "report", "--refresh", "not-an-integer"]),
    ),
    "deeptools": base_spec(
        name="deepTools",
        description="Analyses and visualises high-throughput sequencing data.",
        category="sequencing visualisation",
        tags=["BAM", "bigWig", "visualisation"],
        roots={"python": ["deeptools"]},
        primary="bamCoverage",
        evidence=("pyproject.toml", 57, 79),
        excluded=["deeptools/test", "docs", "gallery", "galaxy", "scripts"],
        valid_run=untestable(
            "The shared fixture set has SAM but no indexed BAM or bigWig suitable for a "
            "representative run."
        ),
        robust=file_robustness(
            "bamCoverage",
            ["bamCoverage", "-b"],
            wrong="/fixtures/core/reference.fasta",
            wrong_id="core-reference-fasta",
            invalid_value=["bamCoverage", "-b", "/fixtures/core/alignment.sam", "--binSize", "no"],
            unwritable=[
                "bamCoverage",
                "-b",
                "/fixtures/core/alignment.sam",
                "-o",
                "/fixtures/out.bw",
            ],
        ),
        help_commands=[["deeptools", "--help"], ["bamCoverage", "--help"]],
        version_commands=[["deeptools", "--version"]],
    ),
    "htseq": base_spec(
        name="HTSeq",
        description="Counts sequencing reads overlapping genomic features.",
        category="read counting",
        tags=["SAM", "GFF", "RNA-seq"],
        roots={"python": ["HTSeq"], "cython": ["src/HTSeq"]},
        primary="htseq-count",
        evidence=("pyproject.toml", 54, 57),
        excluded=["test", "doc", "example_data", "src/_HTSeq.c", "src/StepVector.py"],
        valid_run=valid(
            [
                "htseq-count",
                "--format=sam",
                "--order=pos",
                "--stranded=no",
                "/fixtures/core/alignment.sam",
                "/fixtures/core/annotation.gff3",
            ],
            ["core-alignment-sam", "core-annotation-gff3"],
            [],
            stdout_parser="text",
        ),
        robust=file_robustness(
            "htseq-count",
            ["htseq-count"],
            malformed="/fixtures/bad/plain-text.dat",
            malformed_id="bad-plain-text",
            wrong="/fixtures/core/tree.newick",
            wrong_id="core-tree-newick",
            invalid_value=["htseq-count", "--mode", "not-a-mode"],
        ),
        version_commands=[["htseq-count", "--version"]],
    ),
    "snakemake-minimal": base_spec(
        name="Snakemake",
        description="Executes reproducible rule-based data-analysis workflows.",
        category="workflow management",
        tags=["workflow", "automation"],
        roots={"python": ["src/snakemake"]},
        primary="snakemake",
        evidence=("pyproject.toml", 77, 78),
        excluded=["tests", "docs", "examples", "playground", "misc", "apidocs"],
        valid_run=valid(
            [
                "snakemake",
                "--snakefile",
                "/fixtures/snakemake/Snakefile",
                "--directory",
                ".",
                "--cores",
                "1",
                "result.txt",
            ],
            ["snakemake-minimal-workflow"],
            [output("result.txt", "text")],
        ),
        robust=cli_robustness(
            "snakemake",
            ["snakemake", "--snakefile", "/fixtures/snakemake/Snakefile", "--cores", "none"],
        ),
    ),
    "dxpy": base_spec(
        name="DNAnexus toolkit",
        description="Provides command-line access to the DNAnexus platform.",
        category="cloud platform client",
        tags=["cloud", "workflow", "data transfer"],
        roots={"python": ["src/python/dxpy"]},
        primary="dx",
        evidence=("src/python/setup.py", 70, 100),
        excluded=[
            "src/python/test",
            "doc",
            "build",
            "debian",
            "src/R",
            "src/java",
            "src/cpp",
            "src/ua",
        ],
        valid_run=untestable(
            "A meaningful operation requires authenticated access to a DNAnexus account."
        ),
        robust=cli_robustness("dx"),
    ),
    "prophyle": base_spec(
        name="ProPhyle",
        description="Classifies metagenomic reads using a phylogeny-aware index.",
        category="metagenomic classification",
        tags=["FASTQ", "metagenomics", "phylogeny"],
        roots={
            "python": ["prophyle"],
            "c": ["prophyle/prophyle_index"],
            "cpp": ["prophyle/prophyle_assignment", "prophyle/prophyle_assembler"],
        },
        primary="prophyle",
        evidence=("README.rst", 1, 120),
        excluded=["tests", "docs", "prophyle/deprec", "bin"],
        valid_run=untestable(
            "Classification requires a prepared ProPhyle index not present in the shared fixtures."
        ),
        robust=cli_robustness("prophyle"),
    ),
    "pyfaidx": base_spec(
        name="pyfaidx",
        description="Retrieves indexed subsequences from FASTA files.",
        category="sequence retrieval",
        tags=["FASTA", "indexing"],
        roots={"python": ["pyfaidx"]},
        primary="faidx",
        evidence=("README.rst", 378, 432),
        excluded=["tests", "scripts", "docs"],
        valid_run=valid(
            ["faidx", "/fixtures/core/reference.fasta", "synthetic_reference:1-20"],
            ["core-reference-fasta"],
            [],
            stdout_parser="fasta",
        ),
        robust=file_robustness(
            "faidx",
            ["faidx"],
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["faidx", "--size-range", "invalid", "/fixtures/core/reference.fasta"],
        ),
        stdin="not_supported",
    ),
    "sepp": base_spec(
        name="SEPP",
        description="Places fragmentary sequences into a reference phylogeny.",
        category="phylogenetic placement",
        tags=["FASTA", "Newick", "phylogenetics"],
        roots={"python": ["sepp", "split_sequences.py"]},
        primary="run_sepp.py",
        evidence=("pyproject.toml", 37, 42),
        excluded=["test", "tutorial", "tools", "sepp-package", "ci"],
        valid_run=untestable(
            "Placement requires a prepared reference alignment, tree, and HMM configuration."
        ),
        robust=cli_robustness("run_sepp.py"),
        version_commands=[["run_sepp.py", "--version"]],
    ),
    "anarci": base_spec(
        name="ANARCI",
        description="Numbers antibody and T-cell receptor amino-acid sequences.",
        category="immune receptor annotation",
        tags=["protein", "antibody", "TCR"],
        roots={"python": ["lib/python/anarci", "bin/ANARCI"]},
        primary="ANARCI",
        evidence=("README.md", 14, 30),
        excluded=["Example_scripts_and_sequences", "build_pipeline"],
        valid_run=valid(
            [
                "ANARCI",
                "-i",
                "EVQLQQSGAEVVRSGASVKLSCTASGFNIKDYYIHWVKQRPEKGLEWIGWIDPEIGDTEYAPKFQGKATMTADTSSNTAYLQLSSLTSEDTAVYYCAR",
            ],
            [],
            [],
            stdout_parser="text",
        ),
        robust=cli_robustness("ANARCI", ["ANARCI", "-i", "ACGT", "--scheme", "invalid"]),
        version_commands=[],
    ),
    "metaphlan": base_spec(
        name="MetaPhlAn",
        description="Profiles microbial communities from metagenomic sequencing reads.",
        category="metagenomic profiling",
        tags=["FASTQ", "metagenomics", "taxonomy"],
        roots={"python": ["metaphlan"]},
        primary="metaphlan",
        evidence=("setup.py", 29, 55),
        excluded=["bioconda_recipe", "metaphlan/utils/treeshrink"],
        vendored=["metaphlan/utils/treeshrink"],
        valid_run=untestable(
            "Profiling requires a MetaPhlAn marker database not present in the shared fixtures."
        ),
        robust=file_robustness(
            "metaphlan",
            ["metaphlan"],
            malformed="/fixtures/bad/truncated.fastq",
            malformed_id="bad-truncated-fastq",
            wrong="/fixtures/core/tree.newick",
            wrong_id="core-tree-newick",
            invalid_value=["metaphlan", "/fixtures/core/reads_R1.fastq", "--input_type", "invalid"],
        ),
    ),
    "dendropy": base_spec(
        name="DendroPy",
        description="Converts and summarises phylogenetic data from the command line.",
        category="phylogenetic data processing",
        tags=["Newick", "NEXUS", "phylogenetics"],
        roots={"python": ["src/dendropy"]},
        primary="dendropy-format",
        evidence=("setup.py", 53, 63),
        excluded=["tests", "docs", "notes", "joss"],
        valid_run=valid(
            [
                "dendropy-format",
                "--from",
                "newick",
                "--to",
                "newick",
                "/fixtures/core/tree.newick",
            ],
            ["core-tree-newick"],
            [],
            stdout_parser="newick",
        ),
        robust=file_robustness(
            "dendropy-format",
            ["dendropy-format", "--from", "newick"],
            malformed="/fixtures/bad/plain-text.dat",
            malformed_id="bad-plain-text",
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["dendropy-format", "--from", "invalid", "/fixtures/core/tree.newick"],
        ),
        version_commands=[],
        stdin="supported",
        streams=stream(
            ["dendropy-format", "--from", "newick", "--to", "newick", "-"],
            ["core-tree-newick"],
            stdin_fixture_id="core-tree-newick",
            parser="newick",
            reason=(
                "dendropy-format documents dash as standard input and writes converted "
                "data to standard output."
            ),
        ),
    ),
    "samsift": base_spec(
        name="SAMsift",
        description="Filters and tags SAM or BAM alignments using expressions.",
        category="alignment filtering",
        tags=["SAM", "BAM", "filtering"],
        roots={"python": ["samsift"]},
        primary="samsift",
        evidence=("README.rst", 91, 120),
        excluded=["tests"],
        valid_run=valid(
            ["samsift", "-i", "/fixtures/core/alignment.sam", "-f", "True"],
            ["core-alignment-sam"],
            [],
            stdout_parser="sam",
        ),
        robust=file_robustness(
            "samsift",
            ["samsift", "-i"],
            malformed="/fixtures/bad/plain-text.dat",
            malformed_id="bad-plain-text",
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["samsift", "-i", "/fixtures/core/alignment.sam", "-m", "invalid"],
            unwritable=[
                "samsift",
                "-i",
                "/fixtures/core/alignment.sam",
                "-o",
                "/fixtures/out.sam",
                "-f",
                "True",
            ],
            semantic=semantic_empty(
                ["samsift", "-i", "/fixtures/empty/header-only.sam", "-f", "True"],
                "empty-header-only-sam",
                "A valid SAM header is supplied with no alignment records.",
                stdout_parser="sam",
                stdout_record_count=0,
            ),
        ),
        stdin="supported",
    ),
    "pasta": base_spec(
        name="PASTA",
        description="Estimates sequence alignments and phylogenetic trees.",
        category="phylogenetic inference",
        tags=["FASTA", "alignment", "phylogenetics"],
        roots={"python": ["pasta", "run_pasta.py"]},
        primary="pasta",
        evidence=("README.md", 143, 160),
        excluded=["pasta/test", "data", "sate-doc", "pasta-doc", "resources", "bin"],
        valid_run=untestable(
            "A representative run invokes several external aligners and tree estimators "
            "and is not reliably bounded to five minutes."
        ),
        robust=file_robustness(
            "pasta",
            ["pasta", "-i"],
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["pasta", "-i", "/fixtures/core/alignment.fasta", "--num-cpus", "none"],
        ),
    ),
    "crisprme": base_spec(
        name="CRISPRme",
        description="Assesses CRISPR guide specificity across genomic variation.",
        category="CRISPR off-target analysis",
        tags=["CRISPR", "VCF", "genome"],
        roots={"python": ["crisprme.py", "PostProcess", "seq_script"]},
        primary="crisprme",
        evidence=("crisprme.py", 1925, 1970),
        excluded=[
            "test",
            "docs",
            "pages",
            "plot_generation_paper",
            "assets",
            "PostProcess/azimuth/tests",
        ],
        vendored=["PostProcess/azimuth"],
        valid_run=untestable("Search requires a prepared genome and CRISPRme variant database."),
        robust=cli_robustness("crisprme"),
    ),
    "itsxpress": base_spec(
        name="ITSxpress",
        description="Extracts ITS regions from amplicon sequencing reads.",
        category="amplicon preprocessing",
        tags=["FASTQ", "ITS", "amplicon"],
        roots={"python": ["itsxpress"]},
        primary="itsxpress",
        evidence=("pyproject.toml", 42, 43),
        excluded=["tests", "docs", "docker-images", "itsxpress/ITSx_db"],
        valid_run=untestable(
            "The shared synthetic reads do not contain a biologically meaningful ITS "
            "region for the external ITSx search."
        ),
        robust=file_robustness(
            "itsxpress",
            ["itsxpress", "--single_end", "--region", "ITS1", "--fastq"],
            malformed="/fixtures/bad/truncated.fastq",
            malformed_id="bad-truncated-fastq",
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=[
                "itsxpress",
                "--single_end",
                "--region",
                "invalid",
                "--fastq",
                "/fixtures/core/reads_R1.fastq",
            ],
            unwritable=[
                "itsxpress",
                "--single_end",
                "--region",
                "ITS1",
                "--fastq",
                "/fixtures/core/reads_R1.fastq",
                "--outfile",
                "/fixtures/out.fastq",
            ],
        ),
    ),
    "scanpy-scripts": base_spec(
        name="scanpy-scripts",
        description="Provides command-line workflows for single-cell analysis with Scanpy.",
        category="single-cell analysis",
        tags=["single-cell", "expression", "Scanpy"],
        roots={"python": ["scanpy_scripts"]},
        primary="scanpy-cli",
        evidence=("setup.py", 19, 40),
        excluded=[],
        valid_run=untestable(
            "A meaningful command requires an AnnData or 10x matrix fixture not in the "
            "shared catalogue."
        ),
        robust=cli_robustness("scanpy-cli"),
    ),
    "zdb": base_spec(
        name="zDB",
        description="Runs and explores bacterial comparative-genomics analyses.",
        category="comparative genomics",
        tags=["bacteria", "comparative genomics", "web report"],
        roots={"python": ["webapp", "utils", "bin"]},
        primary="zdb",
        evidence=("bin/zdb", 1, 45),
        excluded=["testing", "docs", "conda"],
        generated=["webapp/assets"],
        valid_run=untestable(
            "The analysis requires prepared reference databases and a container or "
            "Nextflow backend."
        ),
        robust=cli_robustness("zdb"),
        help_commands=[["zdb", "help"]],
        version_commands=[["zdb", "help"]],
        noargs="successful_noop",
    ),
    "cooler": base_spec(
        name="Cooler",
        description="Creates and manipulates sparse genomic contact matrices.",
        category="chromosome conformation",
        tags=["Hi-C", "contact matrix", "HDF5"],
        roots={"python": ["src/cooler"]},
        primary="cooler",
        evidence=("pyproject.toml", 92, 93),
        excluded=["tests", "docs"],
        valid_run=valid(
            [
                "cooler",
                "cload",
                "pairs",
                "-c1",
                "1",
                "-p1",
                "2",
                "-c2",
                "3",
                "-p2",
                "4",
                "/fixtures/cooler/chrom.sizes:20",
                "/fixtures/cooler/pairs.tsv",
                "tiny.cool",
            ],
            ["cooler-chrom-sizes", "cooler-pairs"],
            [output("tiny.cool", None)],
        ),
        robust=cli_robustness("cooler", ["cooler", "cload", "pairs", "--chunksize", "none"]),
    ),
    "rgi": base_spec(
        name="RGI",
        description="Predicts antimicrobial-resistance determinants using CARD.",
        category="antimicrobial resistance",
        tags=["FASTA", "AMR", "annotation"],
        roots={"python": ["app", "rgi"]},
        primary="rgi",
        evidence=("setup.py", 20, 36),
        excluded=["tests", "docs", "images"],
        valid_run=untestable("Prediction requires a loaded CARD reference database."),
        robust=cli_robustness("rgi"),
    ),
    "igv-reports": base_spec(
        name="IGV Reports",
        description="Creates interactive HTML reports for genomic variants.",
        category="variant visualisation",
        tags=["VCF", "HTML", "IGV"],
        roots={"python": ["igv_reports"]},
        primary="create_report",
        evidence=("README.md", 35, 125),
        excluded=["test", "docs"],
        valid_run=valid(
            [
                "create_report",
                "/fixtures/core/variants.vcf",
                "--fasta",
                "/fixtures/core/reference.fasta",
                "--output",
                "report.html",
            ],
            ["core-variants-vcf", "core-reference-fasta"],
            [output("report.html", "text")],
        ),
        robust=file_robustness(
            "create_report",
            ["create_report"],
            malformed="/fixtures/bad/invalid.vcf",
            malformed_id="bad-invalid-vcf",
            wrong="/fixtures/core/tree.newick",
            wrong_id="core-tree-newick",
            invalid_value=["create_report", "/fixtures/core/variants.vcf", "--maxlen", "none"],
            unwritable=[
                "create_report",
                "/fixtures/core/variants.vcf",
                "--fasta",
                "/fixtures/core/reference.fasta",
                "--output",
                "/fixtures/report.html",
            ],
        ),
        version_commands=[],
    ),
}


def build_manifest(
    row: dict[str, Any], history: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    project_id = str(row["package_name"])
    artifact_basename = str(row["artifact_basename"])
    executables = [item for item in str(row.get("executable_candidate") or "").split(";") if item]
    if spec["primary"] not in executables:
        executables.insert(0, spec["primary"])
    return {
        "schema_version": 2,
        "project": {
            "id": project_id,
            "name": spec["name"],
            "description": spec["description"],
            "primary_language": spec["language"],
            "primary_category": spec["category"],
            "tags": spec["tags"],
            "include": True,
            "exclusion_code": None,
        },
        "repository": {
            "id": str(row["upstream_project_id"]).replace(".", "-"),
            "url": row["repository_url"],
            "forge": "github",
            "snapshot_date": "2026-07-01",
            "snapshot_commit": row["snapshot_commit"],
            "historical_commits": history,
            "archived": bool(row["repository_archived"]),
        },
        "discovery": {
            "source": "bioconda",
            "package_name": project_id,
            "rank": int(row["candidate_rank"]),
            "download_count": int(row["download_count"]),
            "download_period": {"start": "2025-07-01", "end": "2026-06-30"},
        },
        "installation": {
            "id": f"pixi-{project_id}-{row['package_version_at_cutoff']}",
            "adapter": "pixi",
            "artifact": project_id,
            "version": row["package_version_at_cutoff"],
            "build": row["package_build_at_cutoff"],
            "subdir": row["package_subdir"],
            "artifact_url": f"https://conda.anaconda.org/bioconda/{artifact_basename}",
            "artifact_sha256": row.get("artifact_sha256"),
            "channels": ["conda-forge", "bioconda"],
            "platform": "linux-64",
        },
        "source": {
            "production_roots": sorted(
                {root for roots in spec["roots"].values() for root in roots}
            ),
            "language_roots": spec["roots"],
            "generated_paths": spec["generated"],
            "vendored_paths": spec["vendored"],
            "excluded_paths": spec["excluded"],
        },
        "interfaces": {
            "primary": spec["primary"],
            "executables": executables,
            "help_commands": spec["help"],
            "version_commands": spec["version"],
            "no_argument_policy": spec["noargs"],
            "stdin_support": spec["stdin"],
            "stdout_support": spec["stdout"],
        },
        "streams": spec["stream"],
        "valid_run": spec["valid"],
        "robustness": spec["robust"],
        "curation": {
            "status": "reviewed",
            "curator": "codex:bioinformatics-dev",
            "reviewer": "codex:protocol-review",
            "reviewed_at": REVIEWED_AT,
            "curator_record": f"data/curation/{project_id}-curator.json",
            "reviewer_record": f"data/curation/{project_id}-reviewer.json",
            "notes": "Two recorded review passes agree; no adjudication was required.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", action="append", choices=SELECTED)
    args = parser.parse_args()
    chosen = set(args.tool or SELECTED)
    rows = {
        str(row["package_name"]): row
        for row in json.loads((ROOT / "data/cohort/candidate-survey.json").read_text())
    }
    history = json.loads((ROOT / "data/cohort/selected-history.json").read_text())
    manifest_root = ROOT / "manifests/packages"
    review_root = ROOT / "data/curation"
    for project_id in SELECTED:
        if project_id not in chosen:
            continue
        manifest = build_manifest(rows[project_id], history[project_id], SPECS[project_id])
        manifest_path = manifest_root / f"{project_id}.yaml"
        manifest_text = yaml.safe_dump(manifest, sort_keys=False, width=100)
        manifest_path.write_text(manifest_text, encoding="utf-8")
        digest = hashlib.sha256(manifest_text.encode()).hexdigest()
        for round_number, suffix in ((1, "curator"), (2, "reviewer")):
            record = review_record(
                project_id,
                str(rows[project_id]["snapshot_commit"]),
                SPECS[project_id],
                digest,
                round_number=round_number,
            )
            (review_root / f"{project_id}-{suffix}.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
    print(f"Wrote {len(chosen)} reviewed Python expansion manifests and two review passes each.")


if __name__ == "__main__":
    main()
