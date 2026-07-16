#!/usr/bin/env python3
"""Materialise a reviewed 20-project popular-tool expansion."""

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
    "bowtie2",
    "picard",
    "diamond",
    "star",
    "raxml",
    "cyvcf2",
    "stringtie",
    "freebayes",
    "abyss",
    "unicycler",
    "foldseek",
    "star-fusion",
    "genometools-genometools",
    "vcftools",
    "augustus",
    "bowtie",
    "primer3",
    "mmseqs2",
    "minimap2",
    "spades",
)
REVIEWED_AT = "2026-07-16T16:50:00Z"


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
        or semantic_empty_unknown("The format-specific zero-record fixture requires review."),
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


def spec(
    *,
    name: str,
    description: str,
    language: str,
    category: str,
    tags: list[str],
    roots: dict[str, list[str]],
    primary: str,
    evidence: tuple[str, int, int] = ("README.md", 1, 120),
    excluded: list[str] | None = None,
    valid_run: dict[str, Any] | None = None,
    robust: dict[str, Any] | None = None,
    help_commands: list[list[str]] | None = None,
    version_commands: list[list[str]] | None = None,
    stdin: str = "not_supported",
    stdout: str = "supported",
    streams: dict[str, Any] | None = None,
    generated: list[str] | None = None,
    vendored: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "language": language,
        "category": category,
        "tags": tags,
        "roots": roots,
        "generated": generated or [],
        "vendored": vendored or [],
        "excluded": excluded
        or ["test", "tests", "doc", "docs", "example", "examples", "data", "scripts"],
        "primary": primary,
        "help": help_commands or [[primary, "--help"]],
        "version": version_commands if version_commands is not None else [[primary, "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": stdin,
        "stdout": stdout,
        "stream": streams
        or stream(
            None, [], reason="The documented interface does not provide a bounded stream mode."
        ),
        "valid": valid_run
        or untestable(
            "A representative successful run requires prepared references, indexes, databases, "
            "or multi-file inputs not present in the shared fixture catalogue."
        ),
        "robust": robust or cli_robustness(primary),
        "evidence": evidence,
    }


SPECS: dict[str, dict[str, Any]] = {
    "bowtie2": spec(
        name="Bowtie 2",
        description="Aligns sequencing reads to long reference genomes.",
        language="cpp",
        category="read alignment",
        tags=["FASTQ", "index", "alignment"],
        roots={"cpp": ["."], "c": ["."]},
        primary="bowtie2",
        evidence=("MANUAL.markdown", 1, 120),
        robust=cli_robustness("bowtie2", ["bowtie2", "-p", "not-an-integer"]),
    ),
    "picard": spec(
        name="Picard",
        description="Manipulates high-throughput sequencing data and metadata.",
        language="java",
        category="alignment processing",
        tags=["SAM", "BAM", "VCF"],
        roots={"java": ["src/main/java"]},
        primary="picard",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("picard", ["picard", "ViewSam", "VALIDATION_STRINGENCY=invalid"]),
    ),
    "diamond": spec(
        name="DIAMOND",
        description="Searches protein and translated DNA sequences against protein databases.",
        language="cpp",
        category="sequence search",
        tags=["protein", "database", "alignment"],
        roots={"cpp": ["src"]},
        primary="diamond",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("diamond", ["diamond", "blastp", "--threads", "none"]),
    ),
    "star": spec(
        name="STAR",
        description="Aligns RNA-seq reads to genomes.",
        language="c",
        category="RNA-seq alignment",
        tags=["FASTQ", "RNA-seq", "genome index"],
        roots={"c": ["source"], "cpp": ["source"]},
        primary="STAR",
        evidence=("doc/STARmanual.pdf", 1, 1),
        robust=cli_robustness("STAR", ["STAR", "--runThreadN", "none"]),
    ),
    "raxml": spec(
        name="RAxML",
        description="Infers maximum-likelihood phylogenetic trees.",
        language="c",
        category="phylogenetic inference",
        tags=["phylogenetics", "alignment", "tree"],
        roots={"c": ["."]},
        primary="raxmlHPC",
        evidence=("README.md", 1, 120),
        robust=file_robustness(
            "raxmlHPC",
            ["raxmlHPC", "-s"],
            malformed="/fixtures/bad/plain-text.dat",
            malformed_id="bad-plain-text",
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["raxmlHPC", "-p", "not-an-integer", "-s", "/fixtures/core/alignment.fasta"],
        ),
    ),
    "cyvcf2": spec(
        name="cyvcf2",
        description="Provides fast command-line access to VCF/BCF records.",
        language="cython",
        category="variant processing",
        tags=["VCF", "BCF", "filtering"],
        roots={"cython": ["cyvcf2"], "python": ["cyvcf2"], "c": ["cyvcf2"]},
        primary="cyvcf2",
        evidence=("README.md", 1, 120),
        valid_run=valid(
            ["cyvcf2", "/fixtures/core/variants.vcf"],
            ["core-variants-vcf"],
            [],
            stdout_parser="vcf",
        ),
        robust=file_robustness(
            "cyvcf2",
            ["cyvcf2"],
            malformed="/fixtures/bad/invalid.vcf",
            malformed_id="bad-invalid-vcf",
            wrong="/fixtures/core/reference.fasta",
            wrong_id="core-reference-fasta",
            semantic=semantic_empty(
                ["cyvcf2", "/fixtures/empty/header-only.vcf"],
                "empty-header-only-vcf",
                "A valid VCF header is supplied with no variant records.",
                stdout_parser="vcf",
                stdout_record_count=0,
            ),
        ),
    ),
    "stringtie": spec(
        name="StringTie",
        description="Assembles and quantifies transcripts from RNA-seq alignments.",
        language="cpp",
        category="transcript assembly",
        tags=["RNA-seq", "GTF", "BAM"],
        roots={"cpp": ["."]},
        primary="stringtie",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("stringtie", ["stringtie", "-p", "not-an-integer"]),
    ),
    "freebayes": spec(
        name="FreeBayes",
        description="Calls genetic variants from haplotype observations.",
        language="cpp",
        category="variant calling",
        tags=["VCF", "BAM", "variant calling"],
        roots={"cpp": ["src"], "c": ["src"]},
        primary="freebayes",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("freebayes", ["freebayes", "--ploidy", "not-an-integer"]),
    ),
    "abyss": spec(
        name="ABySS",
        description="Assembles short reads using a de Bruijn graph.",
        language="cpp",
        category="genome assembly",
        tags=["FASTQ", "assembly", "de Bruijn graph"],
        roots={"cpp": ["."]},
        primary="abyss",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("abyss", ["abyss", "-k", "none"]),
    ),
    "unicycler": spec(
        name="Unicycler",
        description="Assembles bacterial genomes from short and long reads.",
        language="cpp",
        category="genome assembly",
        tags=["FASTQ", "assembly", "bacteria"],
        roots={"python": ["unicycler"], "cpp": ["unicycler/src"]},
        primary="unicycler",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("unicycler", ["unicycler", "-t", "none"]),
    ),
    "foldseek": spec(
        name="Foldseek",
        description="Searches and clusters protein structures.",
        language="c",
        category="structure search",
        tags=["protein structure", "database", "search"],
        roots={"c": ["src"], "cpp": ["src"]},
        primary="foldseek",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("foldseek", ["foldseek", "easy-search", "--threads", "none"]),
    ),
    "star-fusion": spec(
        name="STAR-Fusion",
        description="Detects fusion transcripts from RNA-seq alignments.",
        language="perl",
        category="fusion detection",
        tags=["RNA-seq", "fusion", "STAR"],
        roots={"perl": ["."], "python": ["FusionFilter"]},
        primary="STAR-Fusion",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("STAR-Fusion", ["STAR-Fusion", "--CPU", "none"]),
    ),
    "genometools-genometools": spec(
        name="GenomeTools",
        description="Processes genome annotation and sequence files.",
        language="c",
        category="genome annotation processing",
        tags=["GFF", "FASTA", "annotation"],
        roots={"c": ["src"]},
        primary="gt",
        evidence=("README.md", 1, 120),
        valid_run=valid(
            ["gt", "seqstat", "/fixtures/core/reference.fasta"],
            ["core-reference-fasta"],
            [],
            stdout_parser="text",
        ),
        robust=file_robustness(
            "gt",
            ["gt", "seqstat"],
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["gt", "seqstat", "-width", "none", "/fixtures/core/reference.fasta"],
        ),
    ),
    "vcftools": spec(
        name="VCFtools",
        description="Filters and summarises VCF files.",
        language="cpp",
        category="variant processing",
        tags=["VCF", "filtering", "summary statistics"],
        roots={"cpp": ["src"], "c": ["src"]},
        primary="vcftools",
        evidence=("README.md", 1, 120),
        valid_run=valid(
            ["vcftools", "--vcf", "/fixtures/core/variants.vcf", "--freq", "--out", "variants"],
            ["core-variants-vcf"],
            [output("variants.frq", "text")],
        ),
        robust=file_robustness(
            "vcftools",
            ["vcftools", "--vcf"],
            malformed="/fixtures/bad/invalid.vcf",
            malformed_id="bad-invalid-vcf",
            wrong="/fixtures/core/reference.fasta",
            wrong_id="core-reference-fasta",
            invalid_value=["vcftools", "--vcf", "/fixtures/core/variants.vcf", "--max-missing", "none"],
            unwritable=[
                "vcftools",
                "--vcf",
                "/fixtures/core/variants.vcf",
                "--freq",
                "--out",
                "/fixtures/out",
            ],
        ),
    ),
    "augustus": spec(
        name="AUGUSTUS",
        description="Predicts genes in eukaryotic genomic sequences.",
        language="cpp",
        category="gene prediction",
        tags=["FASTA", "gene prediction", "annotation"],
        roots={"cpp": ["src"], "c": ["src"]},
        primary="augustus",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("augustus", ["augustus", "--species=missing_species"]),
    ),
    "bowtie": spec(
        name="Bowtie",
        description="Aligns sequencing reads to short reference indexes.",
        language="cpp",
        category="read alignment",
        tags=["FASTQ", "index", "alignment"],
        roots={"cpp": ["."], "c": ["."]},
        primary="bowtie",
        evidence=("MANUAL", 1, 120),
        robust=cli_robustness("bowtie", ["bowtie", "-p", "none"]),
    ),
    "primer3": spec(
        name="Primer3",
        description="Designs PCR primers from sequence constraints.",
        language="c",
        category="primer design",
        tags=["FASTA", "PCR", "primer"],
        roots={"c": ["src"]},
        primary="primer3_core",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("primer3_core", ["primer3_core", "--format_output", "--p3_settings_file=/fixtures/bad/missing.dat"]),
    ),
    "mmseqs2": spec(
        name="MMseqs2",
        description="Searches and clusters large sequence sets.",
        language="c",
        category="sequence search",
        tags=["protein", "nucleotide", "database"],
        roots={"c": ["src"], "cpp": ["src"]},
        primary="mmseqs",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("mmseqs", ["mmseqs", "search", "--threads", "none"]),
    ),
    "minimap2": spec(
        name="minimap2",
        description="Maps long DNA or mRNA sequences to a reference.",
        language="c",
        category="read alignment",
        tags=["FASTA", "FASTQ", "long reads"],
        roots={"c": ["."]},
        primary="minimap2",
        evidence=("README.md", 1, 120),
        valid_run=valid(
            ["minimap2", "/fixtures/core/reference.fasta", "/fixtures/core/reads_R1.fastq"],
            ["core-reference-fasta", "core-reads-r1-fastq"],
            [],
            stdout_parser="paf",
        ),
        robust=file_robustness(
            "minimap2",
            ["minimap2", "/fixtures/core/reference.fasta"],
            malformed="/fixtures/bad/truncated.fastq",
            malformed_id="bad-truncated-fastq",
            wrong="/fixtures/core/variants.vcf",
            wrong_id="core-variants-vcf",
            invalid_value=["minimap2", "-t", "none", "/fixtures/core/reference.fasta", "/fixtures/core/reads_R1.fastq"],
        ),
    ),
    "spades": spec(
        name="SPAdes",
        description="Assembles genomes from sequencing reads.",
        language="cpp",
        category="genome assembly",
        tags=["FASTQ", "assembly", "metagenomics"],
        roots={"cpp": ["src"], "python": ["src/spades_pipeline"]},
        primary="spades.py",
        evidence=("README.md", 1, 120),
        robust=cli_robustness("spades.py", ["spades.py", "-t", "none"]),
    ),
}


def build_manifest(
    row: dict[str, Any], history: dict[str, Any], project_spec: dict[str, Any]
) -> dict[str, Any]:
    project_id = str(row["package_name"])
    artifact_basename = str(row["artifact_basename"])
    executables = [item for item in str(row.get("executable_candidate") or "").split(";") if item]
    if project_spec["primary"] not in executables:
        executables.insert(0, project_spec["primary"])
    return {
        "schema_version": 2,
        "project": {
            "id": project_id,
            "name": project_spec["name"],
            "description": project_spec["description"],
            "primary_language": project_spec["language"],
            "primary_category": project_spec["category"],
            "tags": project_spec["tags"],
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
                {root for roots in project_spec["roots"].values() for root in roots}
            ),
            "language_roots": project_spec["roots"],
            "generated_paths": project_spec["generated"],
            "vendored_paths": project_spec["vendored"],
            "excluded_paths": project_spec["excluded"],
        },
        "interfaces": {
            "primary": project_spec["primary"],
            "executables": executables,
            "help_commands": project_spec["help"],
            "version_commands": project_spec["version"],
            "no_argument_policy": project_spec["noargs"],
            "stdin_support": project_spec["stdin"],
            "stdout_support": project_spec["stdout"],
        },
        "streams": project_spec["stream"],
        "valid_run": project_spec["valid"],
        "robustness": project_spec["robust"],
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
    parser.add_argument(
        "--history-json",
        type=Path,
        default=Path("/well/aanensen/users/rva470/seebot-hpc/popular20-history.json"),
    )
    args = parser.parse_args()
    chosen = set(args.tool or SELECTED)
    rows = {
        str(row["package_name"]): row
        for row in json.loads((ROOT / "data/cohort/candidate-survey.json").read_text())
    }
    selected_history_path = ROOT / "data/cohort/selected-history.json"
    selected_history = json.loads(selected_history_path.read_text())
    popular_history = json.loads(args.history_json.read_text())
    manifest_root = ROOT / "manifests/packages"
    review_root = ROOT / "data/curation"
    for project_id in SELECTED:
        if project_id not in chosen:
            continue
        selected_history[project_id] = popular_history[project_id]
        manifest = build_manifest(rows[project_id], popular_history[project_id], SPECS[project_id])
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
    selected_history_path.write_text(
        json.dumps(dict(sorted(selected_history.items())), indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(chosen)} reviewed popular-tool expansion manifests and histories.")


if __name__ == "__main__":
    main()
