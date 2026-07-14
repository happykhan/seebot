"""C and C++ release-source measurements."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seebot.analyzers.command import CommandMeasurement, line_count_parser, run_measurements
from seebot.models import CheckResult


def _cppcheck(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    rows = [line for line in stderr.splitlines() if line.strip()]
    return {"finding_count": len(rows), "findings": rows[:20]}


def _clang(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    rows = [
        line for line in (stdout + stderr).splitlines() if "warning:" in line or "error:" in line
    ]
    return {"diagnostic_count": len(rows), "diagnostics": rows[:20]}


def run_c_cpp_analyzers(
    *,
    source_roots: list[Path],
    language: str,
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_path: Path,
    manifest_sha256: str,
    compile_database: Path | None = None,
    force: bool = False,
) -> list[CheckResult]:
    extensions = ("*.c", "*.h") if language == "c" else ("*.cc", "*.cpp", "*.cxx", "*.hpp", "*.hh")
    files = sorted(
        path for root in source_roots for pattern in extensions for path in root.rglob(pattern)
    )
    prefix = "C" if language == "c" else "CPP"
    paths = [str(path) for path in files]
    clang_command = ["clang-tidy", *paths]
    compile_database = compile_database or next(
        (root for root in source_roots if (root / "compile_commands.json").exists()), None
    )
    if compile_database:
        clang_command.extend(["-p", str(compile_database)])
    doxygen_input = "\n".join(
        [
            "PROJECT_NAME = Seebot audit",
            "QUIET = YES",
            "GENERATE_HTML = NO",
            "GENERATE_LATEX = NO",
            "GENERATE_XML = YES",
            "WARN_IF_UNDOCUMENTED = YES",
            "OUTPUT_DIRECTORY = seebot-doxygen",
            "INPUT = " + " ".join(paths),
        ]
    )
    specs = [
        CommandMeasurement(
            f"{prefix}-CLANGTIDY-001",
            language,
            "clang-tidy",
            clang_command,
            _clang,
            {0, 1},
            untestable_reason=None if compile_database else "compile_commands.json",
        ),
        CommandMeasurement(
            f"{prefix}-CPPCHECK-001",
            language,
            "cppcheck",
            ["cppcheck", "--enable=warning,style,performance,portability", "--xml", *paths],
            _cppcheck,
            {0},
        ),
        CommandMeasurement(
            f"{prefix}-COMPLEXITY-001", language, "pmccabe", ["pmccabe", *paths], line_count_parser
        ),
        CommandMeasurement(
            f"{prefix}-DOXYGEN-001",
            language,
            "doxygen",
            ["doxygen", "-"],
            line_count_parser,
            cwd=source_roots[0] if source_roots else None,
            stdin_text=doxygen_input,
        ),
    ]
    return run_measurements(
        specs,
        package_id=package_id,
        run_id=run_id,
        evidence_root=evidence_root,
        config_path=config_path,
        manifest_sha256=manifest_sha256,
        language=language,
        source_roots=source_roots,
        force=force,
    )
