"""Language-scoped structural measurements over reviewed production source only."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import lizard  # type: ignore[import-untyped]

from seebot.models import CheckResult, Status, ToolIdentity
from seebot.observations import write_measurement

EXTENSIONS = {
    "python": {".py"},
    "cython": {".pyx", ".pxd", ".pxi"},
    "perl": {".pl", ".pm"},
    "c": {".c", ".h"},
    "cpp": {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"},
    "rust": {".rs"},
    "java": {".java"},
}
DEFAULT_EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".pixi",
    "build",
    "dist",
    "target",
    "vendor",
    "vendors",
    "third_party",
    "third-party",
    "external",
    "node_modules",
    "tests",
    "test",
    "t",
    "fixtures",
    "fixture",
    "examples",
    "example",
    "docs",
    "doc",
    "data",
}


def _percentile(values: list[int], proportion: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * proportion)]


def _distribution(values: list[int]) -> dict[str, int | float | None]:
    return {
        "median": float(median(values)) if values else None,
        "percentile_90": _percentile(values, 0.9),
        "maximum": max(values, default=None),
    }


def _is_excluded(path: Path, root: Path, configured: set[str]) -> tuple[bool, str | None]:
    relative = path.relative_to(root).as_posix()
    lowered_parts = {part.lower() for part in path.relative_to(root).parts}
    if lowered_parts & DEFAULT_EXCLUDED_PARTS:
        return True, "standard non-production path"
    if path.name.lower().startswith("test_") or path.name.lower().endswith("_test.py"):
        return True, "test source"
    for prefix in configured:
        normalized = prefix.strip("/")
        if relative == normalized or relative.startswith(normalized + "/"):
            return True, "manifest exclusion"
    return False, None


def production_files(
    checkout: Path, manifest: dict[str, Any], language: str
) -> tuple[list[Path], list[dict[str, str]]]:
    roots = manifest["source"]["language_roots"].get(language, [])
    configured = set(
        manifest["source"]["generated_paths"]
        + manifest["source"]["vendored_paths"]
        + manifest["source"]["excluded_paths"]
    )
    included: list[Path] = []
    excluded: list[dict[str, str]] = []
    for relative_root in roots:
        root = checkout / relative_root
        if not root.exists():
            continue
        explicit_file = root.is_file()
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or (
                not explicit_file and path.suffix.lower() not in EXTENSIONS[language]
            ):
                continue
            is_excluded, reason = _is_excluded(path, checkout, configured)
            if is_excluded:
                excluded.append(
                    {"path": path.relative_to(checkout).as_posix(), "reason": reason or "excluded"}
                )
            else:
                included.append(path)
    return sorted(set(included)), sorted(excluded, key=lambda row: row["path"])


def _documented_python_functions(path: Path) -> tuple[int, int]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return 0, 0
    functions = [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return sum(bool(ast.get_docstring(node)) for node in functions), len(functions)


def _documented_functions(path: Path, language: str, function_count: int) -> tuple[int, int]:
    if language == "python":
        return _documented_python_functions(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    patterns = {
        "perl": r"(?:^=head\w|^=item|^#).{0,300}\n\s*sub\s+\w+",
        "c": r"/\*\*?[\s\S]{0,800}?\*/\s*[\w\s*]+\([^;{}]*\)\s*\{",
        "cpp": r"/\*\*?[\s\S]{0,800}?\*/\s*[\w:<>,~\s*&]+\([^;{}]*\)\s*(?:const\s*)?\{",
        "rust": r"(?:^\s*///.*\n)+\s*(?:pub\s+)?fn\s+\w+",
        "java": (
            r"/\*\*[\s\S]{0,1000}?\*/\s*"
            r"(?:public|protected|private|static|final|\s)+[\w<>\[\]]+\s+\w+\s*\("
        ),
    }
    pattern = patterns.get(language)
    return (len(re.findall(pattern, text, re.MULTILINE)) if pattern else 0, function_count)


def _duplication(files: list[Path], block_size: int = 6) -> dict[str, Any]:
    blocks: Counter[tuple[str, ...]] = Counter()
    total_lines = 0
    for path in files:
        normalized = [
            re.sub(r"\s+", " ", line.strip())
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "//", "/*", "*"))
        ]
        total_lines += len(normalized)
        blocks.update(
            tuple(normalized[index : index + block_size])
            for index in range(len(normalized) - block_size + 1)
        )
    duplicated_blocks = sum(1 for count in blocks.values() if count > 1)
    duplicated_lines = sum(block_size * (count - 1) for count in blocks.values() if count > 1)
    return {
        "block_size_lines": block_size,
        "duplicated_blocks": duplicated_blocks,
        "duplicated_line_percent": round(100 * min(duplicated_lines, total_lines) / total_lines, 3)
        if total_lines
        else 0.0,
        "analyzer": "seebot-exact-normalized-blocks",
    }


def structural_facts(files: list[Path], language: str) -> dict[str, dict[str, Any]]:
    file_lengths: list[int] = []
    functions: list[Any] = []
    nonblank_lines = 0
    documented = 0
    documentable = 0
    for path in files:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        file_lengths.append(len(lines))
        nonblank_lines += sum(bool(line.strip()) for line in lines)
        if language != "cython":
            analysis = lizard.analyze_file(str(path))
            functions.extend(analysis.function_list)
            observed_documented, observed_total = _documented_functions(
                path, language, len(analysis.function_list)
            )
            documented += observed_documented
            documentable += observed_total
    lengths = [int(function.length) for function in functions]
    complexity = [int(function.cyclomatic_complexity) for function in functions]
    nesting = [int(function.max_nesting_depth) for function in functions]
    parameters = [int(function.parameter_count) for function in functions]
    file_distribution = _distribution(file_lengths) | {
        "over_500": sum(value > 500 for value in file_lengths),
        "over_1000": sum(value > 1000 for value in file_lengths),
        "percent_over_500": round(
            100 * sum(value > 500 for value in file_lengths) / len(file_lengths), 3
        )
        if file_lengths
        else 0.0,
        "percent_over_1000": round(
            100 * sum(value > 1000 for value in file_lengths) / len(file_lengths), 3
        )
        if file_lengths
        else 0.0,
    }
    function_distribution = {
        "length_median": float(median(lengths)) if lengths else None,
        "length_percentile_90": _percentile(lengths, 0.9),
        "length_maximum": max(lengths, default=None),
        "over_50_lines": sum(value > 50 for value in lengths),
        "over_100_lines": sum(value > 100 for value in lengths),
        "nesting_maximum": max(nesting, default=None),
        "over_5_parameters": sum(value > 5 for value in parameters),
        "function_count": len(functions),
        "over_50_lines_per_100_functions": round(
            100 * sum(value > 50 for value in lengths) / len(functions), 3
        )
        if functions
        else None,
        "over_5_parameters_per_100_functions": round(
            100 * sum(value > 5 for value in parameters) / len(functions), 3
        )
        if functions
        else None,
    }
    complexity_distribution = _distribution(complexity) | {
        "over_10": sum(value > 10 for value in complexity),
        "over_20": sum(value > 20 for value in complexity),
        "over_10_per_100_functions": round(
            100 * sum(value > 10 for value in complexity) / len(functions), 3
        )
        if functions
        else None,
    }
    return {
        "inventory": {
            "language": language,
            "files": len(files),
            "physical_lines": sum(file_lengths),
            "nonblank_lines": nonblank_lines,
        },
        "files": file_distribution,
        "functions": function_distribution,
        "complexity": complexity_distribution,
        "duplication": _duplication(files),
        "documentation": {
            "documented_functions": documented,
            "documentable_functions": documentable,
            "coverage_percent": round(100 * documented / documentable, 3) if documentable else None,
            "native_measure": "function-associated documentation",
        },
    }


def run_structural_observations(
    *,
    manifest: dict[str, Any],
    checkout: Path,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    snapshot_date: str,
    snapshot_commit: str | None,
    force: bool = False,
) -> list[CheckResult]:
    project_id = manifest["project"]["id"]
    results: list[CheckResult] = []
    checks = {
        "inventory": "SRC-INVENTORY-001",
        "files": "SRC-FILE-LENGTH-001",
        "functions": "SRC-FUNCTION-STRUCTURE-001",
        "complexity": "SRC-COMPLEXITY-001",
        "duplication": "SRC-DUPLICATION-001",
        "documentation": "SRC-DOCUMENTATION-001",
    }
    for language in sorted(manifest["source"]["language_roots"]):
        files, excluded = production_files(checkout, manifest, language)
        facts = structural_facts(files, language)
        facts["inventory"]["included_paths"] = [
            path.relative_to(checkout).as_posix() for path in files
        ]
        facts["inventory"]["excluded_paths"] = excluded
        for family, check_id in checks.items():
            not_applicable = language == "cython" and family in {"functions", "complexity"}
            results.append(
                write_measurement(
                    project_id=project_id,
                    run_id=run_id,
                    check_id=check_id,
                    probe_id=f"source:{language}:{family}",
                    domain="source",
                    status=Status.NOT_APPLICABLE if not_applicable else Status.OBSERVED,
                    observed=facts[family],
                    evidence_root=evidence_root,
                    config_path=config_path,
                    snapshot_date=snapshot_date,
                    snapshot_commit=snapshot_commit,
                    source_component_id=f"{language}:production",
                    tool=ToolIdentity(name="lizard + Seebot structural observer", version="1.23.0"),
                    notes="Cython has a limited structural profile." if not_applicable else None,
                    force=force,
                )
            )
    return results
