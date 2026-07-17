#!/usr/bin/env python3
"""Materialise the reviewed second 20-project cohort expansion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from curate_current_cohort import output, review_record, valid
from curate_popular20_expansion import build_manifest, cli_robustness, file_robustness, spec

ROOT = Path(__file__).resolve().parents[1]
SELECTED = (
    "peptide-shaker",
    "searchgui",
    "slow5tools",
    "muscle",
    "bamtools",
    "sra-tools",
    "gatk4",
    "seqtk",
    "hhsuite",
    "f5c",
    "portcullis",
    "prodigal",
    "trnascan-se",
    "trinity",
    "salmon",
    "infernal",
    "prank",
    "mlst",
    "ngmlr",
    "rsem",
)
REVIEWED_AT = "2026-07-17T10:30:00Z"


SPECS: dict[str, dict[str, Any]] = {
    "peptide-shaker": spec(
        name="PeptideShaker",
        description="Interprets and visualizes proteomics identification results.",
        language="java",
        category="proteomics",
        tags=["mass spectrometry", "proteomics"],
        roots={"java": ["src/main/java"]},
        primary="peptide-shaker",
        evidence=("README.md", 96, 142),
        help_commands=[["peptide-shaker", "eu.isas.peptideshaker.cmd.PeptideShakerCLI", "-help"]],
        version_commands=[],
    ),
    "searchgui": spec(
        name="SearchGUI",
        description="Runs multiple proteomics identification search engines.",
        language="java",
        category="proteomics",
        tags=["mass spectrometry", "search"],
        roots={"java": ["src/main/java"]},
        primary="searchgui",
        evidence=("README.md", 60, 130),
        help_commands=[["searchgui", "eu.isas.searchgui.cmd.SearchCLI", "-help"]],
        version_commands=[],
        vendored=["resources"],
    ),
    "slow5tools": spec(
        name="slow5tools",
        description="Reads, writes, converts, and indexes SLOW5/BLOW5 signal files.",
        language="c",
        category="signal processing",
        tags=["SLOW5", "BLOW5", "nanopore"],
        roots={"c": ["src"]},
        primary="slow5tools",
        evidence=("README.md", 1, 140),
        vendored=["slow5lib"],
    ),
    "muscle": spec(
        name="MUSCLE",
        description="Constructs multiple sequence alignments.",
        language="cpp",
        category="sequence alignment",
        tags=["FASTA", "alignment"],
        roots={"cpp": ["src"]},
        primary="muscle",
        evidence=("README.md", 1, 120),
        help_commands=[["muscle", "-h"]],
        version_commands=[["muscle", "-version"]],
        valid_run=valid(
            [
                "muscle",
                "-align",
                "/fixtures/core/reference.fasta",
                "-output",
                "aligned.fasta",
            ],
            ["core-reference-fasta"],
            [output("aligned.fasta", "fasta")],
        ),
        robust=file_robustness(
            "muscle",
            ["muscle", "-align"],
            invalid_value=["muscle", "-threads", "none"],
        ),
    ),
    "bamtools": spec(
        name="BamTools",
        description="Provides command-line operations over BAM alignment files.",
        language="cpp",
        category="alignment processing",
        tags=["BAM", "alignment"],
        roots={"cpp": ["src", "tools"]},
        primary="bamtools",
        evidence=("README", 1, 120),
        version_commands=[["bamtools", "--version"]],
    ),
    "sra-tools": spec(
        name="SRA Toolkit",
        description="Reads and converts data from the NCBI Sequence Read Archive.",
        language="c",
        category="data retrieval",
        tags=["SRA", "FASTQ"],
        roots={"c": ["libs", "tools", "tools2"], "cpp": ["libs", "tools", "tools2"]},
        primary="fasterq-dump",
        evidence=("README.md", 1, 120),
        excluded=["test", "shared", "scripts", "setup", "ngs"],
    ),
    "gatk4": spec(
        name="GATK",
        description="Provides genome-analysis tools for high-throughput sequencing data.",
        language="java",
        category="variant analysis",
        tags=["VCF", "BAM", "FASTA"],
        roots={"java": ["src/main/java"], "python": ["src/main/python"]},
        primary="gatk",
        evidence=("README.md", 115, 225),
        excluded=["src/test", "src/testUtils", "scripts", "docs", "resources_for_CI"],
    ),
    "seqtk": spec(
        name="Seqtk",
        description="Transforms and samples FASTA and FASTQ sequences.",
        language="c",
        category="sequence manipulation",
        tags=["FASTA", "FASTQ"],
        roots={"c": ["."]},
        primary="seqtk",
        evidence=("README.md", 1, 100),
        help_commands=[["seqtk"]],
        version_commands=[],
        valid_run=valid(
            ["seqtk", "seq", "/fixtures/core/reference.fasta"],
            ["core-reference-fasta"],
            [],
            stdout_parser="fasta",
        ),
        robust=file_robustness("seqtk", ["seqtk", "seq"]),
    ),
    "hhsuite": spec(
        name="HH-suite",
        description="Searches protein profile HMMs for remote homology.",
        language="cpp",
        category="protein homology",
        tags=["protein", "HMM"],
        roots={"cpp": ["src"]},
        primary="hhsearch",
        evidence=("README.md", 1, 140),
        help_commands=[["hhsearch", "-h"]],
        version_commands=[],
    ),
    "f5c": spec(
        name="f5c",
        description="Performs nanopore signal event alignment and methylation calling.",
        language="c",
        category="signal analysis",
        tags=["nanopore", "methylation"],
        roots={"c": ["src"]},
        primary="f5c",
        evidence=("README.md", 1, 150),
        vendored=["slow5lib"],
    ),
    "portcullis": spec(
        name="Portcullis",
        description="Analyzes and filters splice junctions from alignments.",
        language="cpp",
        category="RNA-seq processing",
        tags=["BAM", "splice junctions"],
        roots={"cpp": ["src"]},
        primary="portcullis",
        evidence=("README.md", 1, 140),
        vendored=["deps", "lib"],
    ),
    "prodigal": spec(
        name="Prodigal",
        description="Predicts genes in prokaryotic genomes.",
        language="c",
        category="gene prediction",
        tags=["FASTA", "GFF", "microbial genomics"],
        roots={"c": ["."]},
        primary="prodigal",
        evidence=("README.md", 1, 120),
        help_commands=[["prodigal", "-h"]],
        version_commands=[["prodigal", "-v"]],
        valid_run=valid(
            [
                "prodigal",
                "-p",
                "meta",
                "-i",
                "/fixtures/core/reference.fasta",
                "-o",
                "genes.gff",
                "-f",
                "gff",
            ],
            ["core-reference-fasta"],
            [output("genes.gff", "text")],
        ),
        robust=file_robustness("prodigal", ["prodigal", "-i"]),
    ),
    "trnascan-se": spec(
        name="tRNAscan-SE",
        description="Detects transfer RNA genes in genomic sequences.",
        language="c",
        category="gene prediction",
        tags=["FASTA", "tRNA"],
        roots={"c": ["src"], "perl": ["lib"]},
        primary="tRNAscan-SE",
        evidence=("README", 1, 140),
        valid_run=valid(
            ["tRNAscan-SE", "-o", "trnas.txt", "/fixtures/core/reference.fasta"],
            ["core-reference-fasta"],
            [output("trnas.txt", "text", nonempty=False)],
        ),
        robust=file_robustness("tRNAscan-SE", ["tRNAscan-SE"]),
    ),
    "trinity": spec(
        name="Trinity",
        description="Assembles transcript sequences from RNA-seq reads.",
        language="perl",
        category="transcriptome assembly",
        tags=["FASTQ", "RNA-seq", "assembly"],
        roots={"perl": ["."]},
        primary="Trinity",
        evidence=("Trinity", 226, 525),
        excluded=[
            "Analysis",
            "Docker",
            "sample_data",
            "trinity_ext_sample_data",
            "trinity-plugins",
            "WDL",
            "util",
        ],
        help_commands=[["Trinity", "--show_full_usage_info"]],
        version_commands=[["Trinity", "--version"]],
    ),
    "salmon": spec(
        name="Salmon",
        description="Quantifies transcript abundance from RNA-seq reads.",
        language="rust",
        category="transcript quantification",
        tags=["FASTQ", "RNA-seq", "quantification"],
        roots={"rust": ["crates"]},
        primary="salmon",
        evidence=("README.md", 1, 140),
        valid_run=valid(
            [
                "salmon",
                "index",
                "-t",
                "/fixtures/core/reference.fasta",
                "-i",
                "salmon_index",
            ],
            ["core-reference-fasta"],
            [output("salmon_index/versionInfo.json", "json")],
        ),
        robust=cli_robustness("salmon", ["salmon", "quant", "--threads", "none"]),
    ),
    "infernal": spec(
        name="Infernal",
        description="Searches sequence databases for structured non-coding RNAs.",
        language="c",
        category="RNA homology",
        tags=["RNA", "covariance models"],
        roots={"c": ["src"]},
        primary="cmsearch",
        evidence=("README.md", 1, 120),
        help_commands=[["cmsearch", "-h"]],
        version_commands=[],
    ),
    "prank": spec(
        name="PRANK",
        description="Builds phylogeny-aware multiple sequence alignments.",
        language="cpp",
        category="sequence alignment",
        tags=["FASTA", "alignment", "phylogenetics"],
        roots={"cpp": ["src"]},
        primary="prank",
        evidence=("README.md", 1, 120),
        help_commands=[["prank", "-help"]],
        version_commands=[["prank", "-version"]],
        valid_run=valid(
            ["prank", "-d=/fixtures/core/reference.fasta", "-o=alignment"],
            ["core-reference-fasta"],
            [output("alignment.best.fas", "fasta")],
        ),
        robust=cli_robustness("prank", ["prank", "-threads=none"]),
    ),
    "mlst": spec(
        name="mlst",
        description="Assigns multilocus sequence types to assembled contigs.",
        language="perl",
        category="sequence typing",
        tags=["FASTA", "MLST", "microbial genomics"],
        roots={"perl": ["bin", "perl5/MLST"]},
        primary="mlst",
        evidence=("README.md", 1, 115),
        valid_run=valid(
            ["mlst", "/fixtures/core/reference.fasta"],
            ["core-reference-fasta"],
            [],
            stdout_parser="tsv",
        ),
        robust=file_robustness("mlst", ["mlst"]),
        vendored=["db", "perl5/Path"],
    ),
    "ngmlr": spec(
        name="NGMLR",
        description="Maps long reads with sensitivity around structural variations.",
        language="cpp",
        category="read alignment",
        tags=["FASTA", "FASTQ", "long reads"],
        roots={"cpp": ["src"]},
        primary="ngmlr",
        evidence=("README.md", 1, 140),
        help_commands=[["ngmlr", "-h"]],
        valid_run=valid(
            [
                "ngmlr",
                "-r",
                "/fixtures/core/reference.fasta",
                "-q",
                "/fixtures/core/reads_R1.fastq",
                "-o",
                "alignment.sam",
                "-t",
                "2",
            ],
            ["core-reference-fasta", "core-reads-r1-fastq"],
            [output("alignment.sam", "sam")],
        ),
        robust=file_robustness(
            "ngmlr",
            ["ngmlr", "-r", "/fixtures/core/reference.fasta", "-q"],
            invalid_value=["ngmlr", "-t", "none"],
        ),
        vendored=["lib"],
    ),
    "rsem": spec(
        name="RSEM",
        description="Estimates gene and isoform expression from RNA-seq reads.",
        language="cpp",
        category="transcript quantification",
        tags=["FASTQ", "RNA-seq", "quantification"],
        roots={"cpp": ["."], "perl": ["."]},
        primary="rsem-calculate-expression",
        evidence=("README.md", 92, 285),
        excluded=["boost", "samtools-1.3", "EBSeq", "pRSEM"],
        vendored=["boost", "samtools-1.3"],
    ),
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
    histories = json.loads((ROOT / "data/cohort/selected-history.json").read_text())
    manifest_root = ROOT / "manifests/packages"
    review_root = ROOT / "data/curation"
    for project_id in SELECTED:
        if project_id not in chosen:
            continue
        manifest = build_manifest(rows[project_id], histories[project_id], SPECS[project_id])
        manifest["curation"]["reviewed_at"] = REVIEWED_AT
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
    print(f"Wrote {len(chosen)} reviewed second-expansion manifests and review records.")


if __name__ == "__main__":
    main()
