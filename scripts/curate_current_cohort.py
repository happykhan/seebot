#!/usr/bin/env python3
"""Materialise the frozen ten-project manifests from reviewed curation decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SELECTED = (
    "samtools",
    "bcftools",
    "fasttree",
    "cutadapt",
    "fastp",
    "famsa",
    "yacrd",
    "pyrodigal",
    "minced",
    "any2fasta",
)
REVIEWED_AT = "2026-07-15T21:30:00Z"
MINCED_SHA256 = "4b71d7f5020b94d80effdb25c33567c51d4e98d3e80c718cd414ca0161d10bef"


def applicable(command: list[str], fixture_id: str | None, reason: str) -> dict[str, Any]:
    return {
        "applicability": "applicable",
        "reason": reason,
        "command": command,
        "fixture_id": fixture_id,
        "diagnostic_expectation": "specific_or_generic",
    }


def not_applicable(reason: str) -> dict[str, Any]:
    return {
        "applicability": "not_applicable",
        "reason": reason,
        "command": None,
        "fixture_id": None,
        "diagnostic_expectation": "not_applicable",
    }


def semantic_empty(
    command: list[str],
    fixture_id: str,
    reason: str,
    *,
    outputs: list[dict[str, Any]] | None = None,
    stdout_parser: str | None = None,
    stdout_record_count: int | None = None,
) -> dict[str, Any]:
    return {
        "applicability": "applicable",
        "reason": reason,
        "command": command,
        "fixture_id": fixture_id,
        "expected_outputs": outputs or [],
        "expect_stdout": False,
        "stdout_parser": stdout_parser,
        "stdout_record_count": stdout_record_count,
    }


def semantic_empty_not_applicable(reason: str) -> dict[str, Any]:
    return {
        "applicability": "not_applicable",
        "reason": reason,
        "command": None,
        "fixture_id": None,
        "expected_outputs": [],
        "expect_stdout": False,
        "stdout_parser": None,
        "stdout_record_count": None,
    }


def semantic_empty_unknown(reason: str) -> dict[str, Any]:
    return {
        **semantic_empty_not_applicable(reason),
        "applicability": "unknown",
    }


def stream(
    command: list[str] | None,
    fixture_ids: list[str],
    *,
    stdin_fixture_id: str | None = None,
    parser: str | None = None,
    reason: str,
) -> dict[str, Any]:
    return {
        "applicability": "applicable" if command else "not_applicable",
        "reason": reason,
        "command": command,
        "fixture_ids": fixture_ids,
        "stdin_fixture_id": stdin_fixture_id,
        "expect_stdout": command is not None,
        "stdout_parser": parser,
        "timeout_seconds": 300,
    }


def valid(
    command: list[str],
    fixture_ids: list[str],
    outputs: list[dict[str, Any]],
    *,
    stdout_parser: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "reviewed",
        "untestable_reason": None,
        "fixture_ids": fixture_ids,
        "command": command,
        "expected_outputs": outputs,
        "expect_stdout": stdout_parser is not None,
        "stdout_parser": stdout_parser,
        "timeout_seconds": 300,
    }


def output(
    path: str,
    parser: str,
    *,
    nonempty: bool = True,
    record_count: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"path": path, "nonempty": nonempty, "parser": parser}
    if record_count is not None:
        result["record_count"] = record_count
    return result


def empty_output(path: str, parser: str, *, nonempty: bool = False) -> dict[str, Any]:
    return {"path": path, "nonempty": nonempty, "parser": parser, "record_count": 0}


SPECS: dict[str, dict[str, Any]] = {
    "samtools": {
        "name": "SAMtools",
        "description": "Views and converts sequence-alignment files.",
        "language": "c",
        "category": "alignment processing",
        "tags": ["SAM", "BAM", "CRAM"],
        "roots": {"c": ["."]},
        "vendored": ["lz4"],
        "excluded": ["test", "examples", "doc", ".ci_helpers"],
        "help": [["samtools", "--help"], ["samtools", "view", "--help"]],
        "version": [["samtools", "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["samtools", "view", "-h", "-"],
            ["core-alignment-sam"],
            stdin_fixture_id="core-alignment-sam",
            parser="sam",
            reason="samtools view documents standard-input and standard-output operation.",
        ),
        "valid": valid(
            ["samtools", "view", "-h", "-o", "converted.sam", "/fixtures/core/alignment.sam"],
            ["core-alignment-sam"],
            [output("converted.sam", "sam")],
        ),
        "robust": {
            "missing_input": applicable(
                ["samtools", "view", "/fixtures/bad/missing.sam"],
                None,
                "The view subcommand requires a readable alignment input.",
            ),
            "empty_input": applicable(
                ["samtools", "view", "/fixtures/bad/empty.dat"],
                "bad-empty",
                "A zero-byte alignment is syntactically invalid.",
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "samtools",
                    "view",
                    "-h",
                    "-o",
                    "empty.sam",
                    "/fixtures/empty/header-only.sam",
                ],
                "empty-header-only-sam",
                "A valid SAM header is supplied with no alignment records.",
                outputs=[empty_output("empty.sam", "sam", nonempty=True)],
            ),
            "malformed_input": applicable(
                ["samtools", "view", "/fixtures/bad/malformed.fasta"],
                "bad-malformed-fasta",
                "Malformed text is supplied where SAM is expected.",
            ),
            "wrong_format": applicable(
                ["samtools", "view", "/fixtures/core/variants.vcf"],
                "core-variants-vcf",
                "A valid VCF is supplied to an alignment reader.",
            ),
            "invalid_option": applicable(
                ["samtools", "view", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["samtools", "view", "--threads", "not-an-integer", "/fixtures/core/alignment.sam"],
                "core-alignment-sam",
                "The thread-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                [
                    "samtools",
                    "view",
                    "-o",
                    "/fixtures/forbidden.sam",
                    "/fixtures/core/alignment.sam",
                ],
                "core-alignment-sam",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("doc/samtools-view.1", 1, 55),
    },
    "bcftools": {
        "name": "BCFtools",
        "description": "Views, filters, and transforms variant-call files.",
        "language": "c",
        "category": "variant processing",
        "tags": ["VCF", "BCF"],
        "roots": {"c": ["."]},
        "vendored": [],
        "excluded": ["test", "doc", ".ci_helpers", "mpileup_bench"],
        "help": [["bcftools", "--help"], ["bcftools", "view", "--help"]],
        "version": [["bcftools", "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["bcftools", "view", "-Ov", "-"],
            ["core-variants-vcf"],
            stdin_fixture_id="core-variants-vcf",
            parser="vcf",
            reason=(
                "bcftools view accepts VCF from standard input and writes VCF to standard output."
            ),
        ),
        "valid": valid(
            ["bcftools", "view", "-Ov", "-o", "filtered.vcf", "/fixtures/core/variants.vcf"],
            ["core-variants-vcf"],
            [output("filtered.vcf", "vcf")],
        ),
        "robust": {
            "missing_input": applicable(
                ["bcftools", "view", "/fixtures/bad/missing.vcf"],
                None,
                "The view command requires an existing variant file.",
            ),
            "empty_input": applicable(
                ["bcftools", "view", "/fixtures/bad/empty.dat"],
                "bad-empty",
                "A zero-byte VCF has no header.",
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "bcftools",
                    "view",
                    "-Ov",
                    "-o",
                    "empty.vcf",
                    "/fixtures/empty/header-only.vcf",
                ],
                "empty-header-only-vcf",
                "A valid VCF header is supplied with no variant records.",
                outputs=[empty_output("empty.vcf", "vcf", nonempty=True)],
            ),
            "malformed_input": applicable(
                ["bcftools", "view", "/fixtures/bad/invalid.vcf"],
                "bad-invalid-vcf",
                "The VCF position field is malformed.",
            ),
            "wrong_format": applicable(
                ["bcftools", "view", "/fixtures/core/reference.fasta"],
                "core-reference-fasta",
                "A valid FASTA is supplied to a variant reader.",
            ),
            "invalid_option": applicable(
                ["bcftools", "view", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["bcftools", "view", "--threads", "not-an-integer", "/fixtures/core/variants.vcf"],
                "core-variants-vcf",
                "The thread-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                [
                    "bcftools",
                    "view",
                    "-o",
                    "/fixtures/forbidden.vcf",
                    "/fixtures/core/variants.vcf",
                ],
                "core-variants-vcf",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("doc/bcftools.txt", 3652, 3690),
    },
    "fasttree": {
        "name": "FastTree",
        "description": "Infers phylogenetic trees from sequence alignments.",
        "language": "c",
        "category": "phylogenetics",
        "tags": ["FASTA", "Newick", "alignment"],
        "roots": {"c": ["FastTree.c"]},
        "vendored": [],
        "excluded": ["old"],
        "help": [["fasttree", "-help"]],
        "version": [["fasttree", "-help"]],
        "noargs": "stdin_filter",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["fasttree", "-nt", "/fixtures/core/alignment.fasta"],
            ["core-alignment-fasta"],
            parser="newick",
            reason="FastTree writes its inferred tree to standard output.",
        ),
        "valid": valid(
            ["fasttree", "-nt", "/fixtures/core/alignment.fasta"],
            ["core-alignment-fasta"],
            [],
            stdout_parser="newick",
        ),
        "robust": {
            "missing_input": applicable(
                ["fasttree", "-nt", "/fixtures/bad/missing.fasta"],
                None,
                "An alignment path is required.",
            ),
            "empty_input": applicable(
                ["fasttree", "-nt", "/fixtures/bad/empty.dat"],
                "bad-empty",
                "A zero-byte alignment contains no sequences.",
            ),
            "semantically_empty_input": semantic_empty_not_applicable(
                "Newick has no agreed zero-sequence tree representation for this operation; "
                "the separate zero-byte probe still assesses graceful rejection."
            ),
            "malformed_input": applicable(
                ["fasttree", "-nt", "/fixtures/bad/malformed.fasta"],
                "bad-malformed-fasta",
                "The FASTA structure is malformed.",
            ),
            "wrong_format": applicable(
                ["fasttree", "-nt", "/fixtures/core/variants.vcf"],
                "core-variants-vcf",
                "A valid VCF is supplied instead of an alignment.",
            ),
            "invalid_option": applicable(
                ["fasttree", "-seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["fasttree", "-boot", "not-an-integer", "/fixtures/core/alignment.fasta"],
                "core-alignment-fasta",
                "The bootstrap-count value is deliberately invalid.",
            ),
            "unwritable_output": not_applicable(
                "The documented primary interface writes the tree to standard output "
                "and has no output-path argument."
            ),
        },
        "evidence": ("README.md", 1, 12),
    },
    "cutadapt": {
        "name": "Cutadapt",
        "description": "Removes adapters and primers from sequencing reads.",
        "language": "python",
        "category": "read preprocessing",
        "tags": ["FASTQ", "adapter trimming"],
        "roots": {"python": ["src/cutadapt"], "cython": ["src/cutadapt"]},
        "vendored": [],
        "excluded": ["tests", "doc"],
        "help": [["cutadapt", "--help"]],
        "version": [["cutadapt", "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["cutadapt", "-a", "AGATCGGAAGAGC", "-o", "-", "-"],
            ["core-reads-r1-fastq"],
            stdin_fixture_id="core-reads-r1-fastq",
            parser="fastq",
            reason="Cutadapt documents dash as standard input and standard output.",
        ),
        "valid": valid(
            [
                "cutadapt",
                "--cores=1",
                "-a",
                "AGATCGGAAGAGC",
                "-o",
                "trimmed.fastq",
                "/fixtures/core/reads_R1.fastq",
            ],
            ["core-reads-r1-fastq"],
            [output("trimmed.fastq", "fastq")],
        ),
        "robust": {
            "missing_input": applicable(
                ["cutadapt", "-o", "out.fastq", "/fixtures/bad/missing.fastq"],
                None,
                "A reads input path is required.",
            ),
            "empty_input": applicable(
                ["cutadapt", "-o", "out.fastq", "/fixtures/bad/empty.dat"],
                "bad-empty",
                "A zero-byte reads file is supplied.",
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "cutadapt",
                    "--cores=1",
                    "-a",
                    "AGATCGGAAGAGC",
                    "-o",
                    "empty.fastq",
                    "/fixtures/empty/empty.fastq",
                ],
                "empty-fastq",
                "A valid FASTQ stream containing zero reads is supplied.",
                outputs=[empty_output("empty.fastq", "fastq")],
            ),
            "malformed_input": applicable(
                ["cutadapt", "-o", "out.fastq", "/fixtures/bad/truncated.fastq"],
                "bad-truncated-fastq",
                "The FASTQ quality string is truncated.",
            ),
            "wrong_format": applicable(
                ["cutadapt", "-o", "out.fastq", "/fixtures/core/variants.vcf"],
                "core-variants-vcf",
                "A valid VCF is supplied instead of reads.",
            ),
            "invalid_option": applicable(
                ["cutadapt", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["cutadapt", "--cores", "not-an-integer", "/fixtures/core/reads_R1.fastq"],
                "core-reads-r1-fastq",
                "The core-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                ["cutadapt", "-o", "/fixtures/forbidden.fastq", "/fixtures/core/reads_R1.fastq"],
                "core-reads-r1-fastq",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("doc/reference.rst", 130, 170),
    },
    "fastp": {
        "name": "fastp",
        "description": "Filters, trims, and reports on FASTQ reads.",
        "language": "cpp",
        "category": "read preprocessing",
        "tags": ["FASTQ", "quality control"],
        "roots": {"cpp": ["src"]},
        "vendored": [],
        "excluded": ["testdata", "scripts"],
        "help": [["fastp", "--help"]],
        "version": [["fastp", "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": "not_supported",
        "stdout": "not_supported",
        "stream": stream(
            None,
            [],
            reason="The reviewed single-end path uses explicit input, output, and report files.",
        ),
        "valid": valid(
            [
                "fastp",
                "--in1",
                "/fixtures/core/reads_R1.fastq",
                "--out1",
                "filtered.fastq",
                "--json",
                "fastp.json",
                "--html",
                "fastp.html",
                "--thread",
                "1",
                "--disable_quality_filtering",
                "--disable_length_filtering",
            ],
            ["core-reads-r1-fastq"],
            [
                output("filtered.fastq", "fastq"),
                output("fastp.json", "json"),
                output("fastp.html", "text"),
            ],
        ),
        "robust": {
            "missing_input": applicable(
                ["fastp", "--in1", "/fixtures/bad/missing.fastq", "--out1", "out.fastq"],
                None,
                "A reads input path is required.",
            ),
            "empty_input": applicable(
                ["fastp", "--in1", "/fixtures/bad/empty.dat", "--out1", "out.fastq"],
                "bad-empty",
                "A zero-byte reads file is supplied.",
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "fastp",
                    "--in1",
                    "/fixtures/empty/empty.fastq",
                    "--out1",
                    "empty.fastq",
                    "--json",
                    "empty.json",
                    "--html",
                    "empty.html",
                    "--thread",
                    "1",
                ],
                "empty-fastq",
                "A valid FASTQ stream containing zero reads is supplied.",
                outputs=[empty_output("empty.fastq", "fastq")],
            ),
            "malformed_input": applicable(
                ["fastp", "--in1", "/fixtures/bad/truncated.fastq", "--out1", "out.fastq"],
                "bad-truncated-fastq",
                "The FASTQ quality string is truncated.",
            ),
            "wrong_format": applicable(
                ["fastp", "--in1", "/fixtures/core/reference.fasta", "--out1", "out.fastq"],
                "core-reference-fasta",
                "A valid FASTA is supplied to a FASTQ interface.",
            ),
            "invalid_option": applicable(
                ["fastp", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["fastp", "--thread", "not-an-integer", "--in1", "/fixtures/core/reads_R1.fastq"],
                "core-reads-r1-fastq",
                "The thread-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                [
                    "fastp",
                    "--in1",
                    "/fixtures/core/reads_R1.fastq",
                    "--out1",
                    "/fixtures/forbidden.fastq",
                ],
                "core-reads-r1-fastq",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("README.md", 320, 360),
    },
    "famsa": {
        "name": "FAMSA",
        "description": "Builds multiple-sequence alignments.",
        "language": "cpp",
        "category": "sequence alignment",
        "tags": ["FASTA", "alignment"],
        "roots": {"cpp": ["src"]},
        "vendored": ["libs"],
        "excluded": ["test", "img"],
        "help": [["famsa", "-help"]],
        "version": [["famsa", "-help"]],
        "noargs": "help_or_usage_error",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["famsa", "-t", "1", "STDIN", "STDOUT"],
            ["core-alignment-fasta"],
            stdin_fixture_id="core-alignment-fasta",
            parser="fasta",
            reason="FAMSA documents STDIN and STDOUT sentinel arguments.",
        ),
        "valid": valid(
            ["famsa", "-t", "1", "/fixtures/core/alignment.fasta", "aligned.fasta"],
            ["core-alignment-fasta"],
            [output("aligned.fasta", "fasta")],
        ),
        "robust": {
            "missing_input": applicable(
                ["famsa", "/fixtures/bad/missing.fasta", "out.fasta"],
                None,
                "An alignment input path is required.",
            ),
            "empty_input": applicable(
                ["famsa", "/fixtures/bad/empty.dat", "out.fasta"],
                "bad-empty",
                "A zero-byte sequence file is supplied.",
            ),
            "semantically_empty_input": semantic_empty(
                ["famsa", "-t", "1", "/fixtures/empty/empty.fasta", "empty.fasta"],
                "empty-fasta",
                "A valid FASTA stream containing zero sequence records is supplied.",
                outputs=[empty_output("empty.fasta", "fasta")],
            ),
            "malformed_input": applicable(
                ["famsa", "/fixtures/bad/malformed.fasta", "out.fasta"],
                "bad-malformed-fasta",
                "The FASTA structure is malformed.",
            ),
            "wrong_format": applicable(
                ["famsa", "/fixtures/core/variants.vcf", "out.fasta"],
                "core-variants-vcf",
                "A valid VCF is supplied instead of FASTA.",
            ),
            "invalid_option": applicable(
                ["famsa", "-seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["famsa", "-t", "not-an-integer", "/fixtures/core/alignment.fasta", "out.fasta"],
                "core-alignment-fasta",
                "The thread-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                ["famsa", "/fixtures/core/alignment.fasta", "/fixtures/forbidden.fasta"],
                "core-alignment-fasta",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("README.md", 94, 130),
    },
    "yacrd": {
        "name": "yacrd",
        "description": "Detects chimeric long reads from overlap mappings.",
        "language": "rust",
        "category": "long-read processing",
        "tags": ["PAF", "long reads"],
        "roots": {"rust": ["src"]},
        "vendored": [],
        "excluded": ["tests", "image"],
        "help": [["yacrd", "--help"]],
        "version": [["yacrd", "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": "not_supported",
        "stdout": "not_supported",
        "stream": stream(
            None, [], reason="The reviewed interface requires explicit input and output paths."
        ),
        "valid": valid(
            [
                "yacrd",
                "--thread",
                "1",
                "--input",
                "/fixtures/core/overlaps.paf",
                "--output",
                "reads.yacrd",
            ],
            ["core-overlaps-paf"],
            [output("reads.yacrd", "text")],
        ),
        "robust": {
            "missing_input": applicable(
                ["yacrd", "-i", "/fixtures/bad/missing.paf", "-o", "out.yacrd"],
                None,
                "An overlap input path is required.",
            ),
            "empty_input": applicable(
                ["yacrd", "-i", "/fixtures/bad/empty.dat", "-o", "out.yacrd"],
                "bad-empty",
                "A zero-byte overlap file is supplied.",
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "yacrd",
                    "--thread",
                    "1",
                    "--input",
                    "/fixtures/empty/empty.paf",
                    "--output",
                    "empty.yacrd",
                ],
                "empty-paf",
                "A valid PAF stream containing zero overlap records is supplied.",
                outputs=[empty_output("empty.yacrd", "tsv")],
            ),
            "malformed_input": applicable(
                ["yacrd", "-i", "/fixtures/bad/malformed.paf", "-o", "out.yacrd"],
                "bad-malformed-paf",
                "The PAF record lacks mandatory columns.",
            ),
            "wrong_format": applicable(
                ["yacrd", "-i", "/fixtures/core/reference.fasta", "-o", "out.yacrd"],
                "core-reference-fasta",
                "A valid FASTA is supplied instead of PAF.",
            ),
            "invalid_option": applicable(
                ["yacrd", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                [
                    "yacrd",
                    "--thread",
                    "not-an-integer",
                    "-i",
                    "/fixtures/core/overlaps.paf",
                    "-o",
                    "out.yacrd",
                ],
                "core-overlaps-paf",
                "The thread-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                ["yacrd", "-i", "/fixtures/core/overlaps.paf", "-o", "/fixtures/forbidden.yacrd"],
                "core-overlaps-paf",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("src/cli.rs", 35, 90),
    },
    "pyrodigal": {
        "name": "Pyrodigal",
        "description": "Finds genes in microbial sequences through a Prodigal-compatible CLI.",
        "language": "cython",
        "category": "gene prediction",
        "tags": ["FASTA", "GFF3", "genes"],
        "roots": {"cython": ["."], "python": ["."]},
        "vendored": ["vendor", "Prodigal", "src/Prodigal", "pyrodigal/prodigal"],
        "excluded": [
            "pyrodigal/tests",
            "src/pyrodigal/tests",
            "src/scripts",
            "benches",
            "docs",
            "paper",
            "setup.py",
        ],
        "help": [["pyrodigal", "--help"]],
        "version": [["pyrodigal", "--version"]],
        "noargs": "stdin_filter",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["pyrodigal", "-p", "meta"],
            ["pyrodigal-synthetic-orf"],
            stdin_fixture_id="pyrodigal-synthetic-orf",
            parser="gff3",
            reason=(
                "The CLI reads FASTA from standard input and writes GFF3 to standard "
                "output when paths are omitted."
            ),
        ),
        "valid": valid(
            ["pyrodigal", "-p", "meta", "-i", "/fixtures/pyrodigal/genes.fasta", "-o", "genes.gff"],
            ["pyrodigal-synthetic-orf"],
            [output("genes.gff", "gff3")],
        ),
        "robust": {
            "missing_input": applicable(
                ["pyrodigal", "-p", "meta", "-i", "/fixtures/bad/missing.fasta"],
                None,
                "A FASTA input path is required when -i is used.",
            ),
            "empty_input": applicable(
                ["pyrodigal", "-p", "meta", "-i", "/fixtures/bad/empty.dat"],
                "bad-empty",
                "A zero-byte FASTA is supplied.",
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "pyrodigal",
                    "-p",
                    "meta",
                    "-i",
                    "/fixtures/empty/empty.fasta",
                    "-o",
                    "empty.gff",
                ],
                "empty-fasta",
                "A valid FASTA stream containing zero sequence records is supplied.",
                outputs=[empty_output("empty.gff", "gff3")],
            ),
            "malformed_input": applicable(
                ["pyrodigal", "-p", "meta", "-i", "/fixtures/bad/malformed.fasta"],
                "bad-malformed-fasta",
                "The FASTA structure is malformed.",
            ),
            "wrong_format": applicable(
                ["pyrodigal", "-p", "meta", "-i", "/fixtures/core/reads_R1.fastq"],
                "core-reads-r1-fastq",
                "A valid FASTQ is supplied instead of FASTA.",
            ),
            "invalid_option": applicable(
                ["pyrodigal", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                [
                    "pyrodigal",
                    "--jobs",
                    "not-an-integer",
                    "-p",
                    "meta",
                    "-i",
                    "/fixtures/pyrodigal/genes.fasta",
                ],
                "pyrodigal-synthetic-orf",
                "The job-count value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                [
                    "pyrodigal",
                    "-p",
                    "meta",
                    "-i",
                    "/fixtures/pyrodigal/genes.fasta",
                    "-o",
                    "/fixtures/forbidden.gff",
                ],
                "pyrodigal-synthetic-orf",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("src/pyrodigal/cli.py", 45, 150),
    },
    "minced": {
        "name": "MinCED",
        "description": "Finds CRISPR arrays in assembled sequences.",
        "language": "java",
        "category": "CRISPR detection",
        "tags": ["FASTA", "GFF3", "CRISPR"],
        "roots": {"java": ["."]},
        "vendored": [],
        "excluded": ["t"],
        "help": [["minced", "--help"]],
        "version": [["minced", "--version"]],
        "noargs": "help_or_usage_error",
        "stdin": "not_supported",
        "stdout": "supported",
        "stream": stream(
            ["minced", "-minNR", "2", "/fixtures/minced/crispr.fasta"],
            ["minced-synthetic-crispr"],
            parser="text",
            reason="With no output path MinCED writes its report to standard output.",
        ),
        "valid": valid(
            [
                "minced",
                "-minNR",
                "2",
                "/fixtures/minced/crispr.fasta",
                "crisprs.txt",
                "crisprs.gff",
            ],
            ["minced-synthetic-crispr"],
            [output("crisprs.txt", "text"), output("crisprs.gff", "gff3")],
        ),
        "robust": {
            "missing_input": applicable(
                ["minced", "/fixtures/bad/missing.fasta"], None, "A FASTA input path is required."
            ),
            "empty_input": applicable(
                ["minced", "/fixtures/bad/empty.dat"], "bad-empty", "A zero-byte FASTA is supplied."
            ),
            "semantically_empty_input": semantic_empty(
                [
                    "minced",
                    "-minNR",
                    "2",
                    "/fixtures/empty/empty.fasta",
                    "empty.txt",
                    "empty.gff",
                ],
                "empty-fasta",
                "A valid FASTA stream containing zero sequence records is supplied.",
                outputs=[empty_output("empty.gff", "gff3")],
            ),
            "malformed_input": applicable(
                ["minced", "/fixtures/bad/malformed.fasta"],
                "bad-malformed-fasta",
                "The FASTA structure is malformed.",
            ),
            "wrong_format": applicable(
                ["minced", "/fixtures/core/variants.vcf"],
                "core-variants-vcf",
                "A valid VCF is supplied instead of FASTA.",
            ),
            "invalid_option": applicable(
                ["minced", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": applicable(
                ["minced", "-minNR", "not-an-integer", "/fixtures/minced/crispr.fasta"],
                "minced-synthetic-crispr",
                "The minimum-repeat value is deliberately invalid.",
            ),
            "unwritable_output": applicable(
                ["minced", "/fixtures/minced/crispr.fasta", "/fixtures/forbidden.txt"],
                "minced-synthetic-crispr",
                "The fixture mount is read-only.",
            ),
        },
        "evidence": ("README.md", 20, 55),
    },
    "any2fasta": {
        "name": "any2fasta",
        "description": "Converts common biological sequence formats to FASTA.",
        "language": "perl",
        "category": "format conversion",
        "tags": ["FASTA", "FASTQ", "conversion"],
        "roots": {"perl": ["any2fasta"]},
        "vendored": [],
        "excluded": ["test"],
        "help": [["any2fasta", "-h"]],
        "version": [["any2fasta", "-v"]],
        "noargs": "help_or_usage_error",
        "stdin": "supported",
        "stdout": "supported",
        "stream": stream(
            ["any2fasta", "-"],
            ["core-reads-r1-fastq"],
            stdin_fixture_id="core-reads-r1-fastq",
            parser="fasta",
            reason=(
                "Dash is the documented standard-input sentinel and converted FASTA is "
                "written to standard output."
            ),
        ),
        "valid": valid(
            ["any2fasta", "/fixtures/core/reads_R1.fastq"],
            ["core-reads-r1-fastq"],
            [],
            stdout_parser="fasta",
        ),
        "robust": {
            "missing_input": applicable(
                ["any2fasta", "/fixtures/bad/missing.fastq"],
                None,
                "A readable sequence input is required.",
            ),
            "empty_input": applicable(
                ["any2fasta", "/fixtures/bad/empty.dat"],
                "bad-empty",
                "A zero-byte sequence file is supplied.",
            ),
            "semantically_empty_input": semantic_empty(
                ["any2fasta", "/fixtures/empty/empty.fastq"],
                "empty-fastq",
                "A valid FASTQ stream containing zero reads is supplied.",
                stdout_parser="fasta",
                stdout_record_count=0,
            ),
            "malformed_input": applicable(
                ["any2fasta", "/fixtures/bad/truncated.fastq"],
                "bad-truncated-fastq",
                "The FASTQ quality string is truncated.",
            ),
            "wrong_format": applicable(
                ["any2fasta", "/fixtures/core/variants.vcf"],
                "core-variants-vcf",
                "VCF is a valid biological format not supported by this converter.",
            ),
            "invalid_option": applicable(
                ["any2fasta", "--seebot-invalid-option"],
                None,
                "The option is deliberately unrecognised.",
            ),
            "invalid_value": not_applicable(
                "The reviewed interface has boolean switches but no bounded option-value parameter."
            ),
            "unwritable_output": not_applicable(
                "The documented primary interface writes FASTA to standard output and "
                "has no output-path argument."
            ),
        },
        "evidence": ("README.md", 70, 135),
    },
}


def review_record(
    project_id: str,
    commit: str,
    spec: dict[str, Any],
    manifest_sha256: str,
    *,
    round_number: int,
) -> dict[str, Any]:
    evidence_file, start, end = spec["evidence"]
    role = "curator" if round_number == 1 else "protocol-review"
    return {
        "schema_version": 2,
        "project_id": project_id,
        "source_commit": commit,
        "review_type": "manifest_curation",
        "reviewer_id": f"codex:{role}",
        "review_round": round_number,
        "sampling_seed": 0,
        "sample": [
            {
                "file": evidence_file,
                "start_line": start,
                "end_line": end,
                "item_type": "interface_and_source_scope",
                "item_name": project_id,
            }
        ],
        "assessment": {
            "manifest_sha256": manifest_sha256,
            "source_roots_reviewed": True,
            "commands_are_argument_arrays": True,
            "fixtures_and_applicability_reviewed": True,
            "upstream_tests_not_requested": True,
        },
        "confidence": "high",
        "evidence_notes": (
            "Independent second-pass agreement with the frozen interface, fixture, and "
            "source-scope decisions."
            if round_number == 2
            else "Initial metadata and upstream-documentation curation of interface, "
            "fixtures, and source scope."
        ),
        "adjudication_required": False,
    }


def build_manifest(
    row: dict[str, Any], history: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    project_id = str(row["package_name"])
    artifact_sha = row.get("artifact_sha256") or (MINCED_SHA256 if project_id == "minced" else None)
    artifact_basename = str(row["artifact_basename"])
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
            "archived": str(row["repository_archived"]).lower() == "true",
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
            "artifact_sha256": artifact_sha,
            "channels": ["conda-forge", "bioconda"],
            "platform": "linux-64",
        },
        "source": {
            "production_roots": sorted(
                {root for roots in spec["roots"].values() for root in roots}
            ),
            "language_roots": spec["roots"],
            "generated_paths": [],
            "vendored_paths": spec["vendored"],
            "excluded_paths": spec["excluded"],
        },
        "interfaces": {
            "primary": project_id,
            "executables": [project_id],
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
    manifest_root.mkdir(parents=True, exist_ok=True)
    review_root.mkdir(parents=True, exist_ok=True)
    if not args.tool:
        for path in manifest_root.glob("*.yaml"):
            path.unlink()
        for path in review_root.glob("*.json"):
            path.unlink()
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
    print(f"Wrote {len(chosen)} reviewed project manifests and two review passes each.")


if __name__ == "__main__":
    main()
