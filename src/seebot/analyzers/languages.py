"""Registry and dispatch for reviewed release-source language roots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seebot.analyzers.c_cpp import run_c_cpp_analyzers
from seebot.analyzers.perl import run_perl_analyzers
from seebot.analyzers.python import run_python_analyzers
from seebot.analyzers.rust import run_rust_analyzers
from seebot.analyzers.universal import run_universal_analyzers
from seebot.models import CheckResult

SUPPORTED_LANGUAGES = ("python", "perl", "c", "cpp", "rust")


def reviewed_language_roots(manifest: dict[str, Any], extracted: Path) -> dict[str, list[Path]]:
    configured = manifest["source_layout"].get("language_roots", {})
    return {
        language: [extracted / Path(value) for value in configured.get(language, [])]
        for language in SUPPORTED_LANGUAGES
        if configured.get(language)
    }


def run_language_analyzers(
    *,
    language: str,
    source_roots: list[Path],
    package_id: str,
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    manifest_sha256: str,
    force: bool = False,
) -> list[CheckResult]:
    if language == "python":
        results = run_python_analyzers(
            source_roots=source_roots,
            package_id=package_id,
            run_id=run_id,
            evidence_root=evidence_root,
            config_root=config_root,
            manifest_sha256=manifest_sha256,
            force=force,
        )
    elif language == "perl":
        results = run_perl_analyzers(
            source_roots=source_roots,
            package_id=package_id,
            run_id=run_id,
            evidence_root=evidence_root,
            config_path=config_root / "perlcritic-standard.rc",
            manifest_sha256=manifest_sha256,
            force=force,
        )
    elif language in {"c", "cpp"}:
        results = run_c_cpp_analyzers(
            source_roots=source_roots,
            language=language,
            package_id=package_id,
            run_id=run_id,
            evidence_root=evidence_root,
            config_path=config_root / "audit.yaml",
            manifest_sha256=manifest_sha256,
            force=force,
        )
    elif language == "rust":
        results = run_rust_analyzers(
            source_roots=source_roots,
            package_id=package_id,
            run_id=run_id,
            evidence_root=evidence_root,
            config_path=config_root / "audit.yaml",
            manifest_sha256=manifest_sha256,
            force=force,
        )
    else:
        raise ValueError(f"Unsupported language: {language}")
    results.extend(
        run_universal_analyzers(
            source_roots=source_roots,
            language=language,
            package_id=package_id,
            run_id=run_id,
            evidence_root=evidence_root,
            config_path=config_root / "audit.yaml",
            manifest_sha256=manifest_sha256,
            force=force,
        )
    )
    return results
