"""Conservative language and source-role classification."""

from __future__ import annotations

from pathlib import Path

LANGUAGE_SUFFIXES = {
    ".py": "python",
    ".pyi": "python",
    ".pyx": "cython",
    ".pxd": "cython",
    ".pl": "perl",
    ".pm": "perl",
    ".t": "perl",
    ".c": "c",
    ".h": "c_or_cpp_header",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".rs": "rust",
}


def classify_language(path: Path) -> str | None:
    return LANGUAGE_SUFFIXES.get(path.suffix.lower())


def classify_role(
    path: Path,
    *,
    test_paths: list[Path] | None = None,
    documentation_paths: list[Path] | None = None,
    generated_paths: list[Path] | None = None,
    vendored_paths: list[Path] | None = None,
) -> str:
    groups = (
        ("vendored", vendored_paths or []),
        ("generated", generated_paths or []),
        ("test", test_paths or []),
        ("documentation", documentation_paths or []),
    )
    for role, roots in groups:
        if any(path == root or path.is_relative_to(root) for root in roots):
            return role
    return "production"
