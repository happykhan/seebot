"""Pinned native lint and security findings for non-Python source components."""

from __future__ import annotations

import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot import __version__
from seebot.evidence import audit_code_identity, evidence_path, sha256_file
from seebot.models import CheckResult, EvidencePaths, ResultKind, Status, ToolIdentity
from seebot.observations import write_measurement
from seebot.runtime.analyzers import AnalyzerEnvironment, analyzer_command

Parser = Callable[[str, str, int], tuple[dict[str, Any], Status]]
SECURITY_CPP_IDS = re.compile(
    r"buffer|null|uninit|useafter|dangling|leak|overflow|invalid|race|unsafe|insecure",
    re.IGNORECASE,
)


def _density(count: int, lines: int) -> float | None:
    return round(1000 * count / lines, 3) if lines else None


def _lines(files: list[Path]) -> int:
    return sum(
        bool(line.strip()) and not line.lstrip().startswith(("#", "//", "/*", "*"))
        for path in files
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
    )


def _perlcritic_parser(lines: int) -> Parser:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        findings: Counter[tuple[str, str]] = Counter()
        for row in (stdout + stderr).splitlines():
            parts = row.split("~|~")
            if len(parts) >= 3:
                findings[(parts[0], parts[2])] += 1
        count = sum(findings.values())
        return (
            {
                "language": "perl",
                "analyzer": "Perl::Critic",
                "finding_count": count,
                "findings_per_kloc": _density(count, lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_severity": severity,
                        "count": observed,
                        "findings_per_kloc": _density(observed, lines),
                    }
                    for (rule, severity), observed in sorted(findings.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _cppcheck_parser(lines: int, *, security_only: bool) -> Parser:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        root = ET.fromstring(stderr or "<results><errors /></results>")
        findings: Counter[tuple[str, str]] = Counter()
        for error in root.findall(".//error"):
            rule = error.attrib.get("id", "UNKNOWN")
            if security_only and not SECURITY_CPP_IDS.search(rule):
                continue
            findings[(rule, error.attrib.get("severity", "UNKNOWN"))] += 1
        count = sum(findings.values())
        return (
            {
                "analyzer": "cppcheck",
                "security_rule_filter": SECURITY_CPP_IDS.pattern if security_only else None,
                "finding_count": count,
                "findings_per_kloc": _density(count, lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_severity": severity,
                        "count": observed,
                        "findings_per_kloc": _density(observed, lines),
                    }
                    for (rule, severity), observed in sorted(findings.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _pmd_parser(lines: int, language: str) -> Parser:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        payload = json.loads(stdout or "{}")
        findings: Counter[tuple[str, str]] = Counter()
        for file_row in payload.get("files", []):
            for violation in file_row.get("violations", []):
                findings[
                    (
                        str(violation.get("rule", "UNKNOWN")),
                        str(violation.get("priority", "UNKNOWN")),
                    )
                ] += 1
        count = sum(findings.values())
        return (
            {
                "language": language,
                "analyzer": "PMD",
                "finding_count": count,
                "findings_per_kloc": _density(count, lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_severity": priority,
                        "count": observed,
                        "findings_per_kloc": _density(observed, lines),
                    }
                    for (rule, priority), observed in sorted(findings.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _clippy_parser(lines: int) -> Parser:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        text = stdout + stderr
        if any(
            phrase in text.lower()
            for phrase in ("failed to download", "no matching package", "offline mode")
        ):
            return ({"analyzer": "clippy", "dependency_cache_available": False}, Status.UNTESTABLE)
        findings: Counter[tuple[str, str]] = Counter()
        for line in stdout.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = row.get("message") if isinstance(row, dict) else None
            if not isinstance(message, dict):
                continue
            code = message.get("code") or {}
            rule = code.get("code") if isinstance(code, dict) else None
            if rule:
                findings[(str(rule), str(message.get("level", "UNKNOWN")))] += 1
        count = sum(findings.values())
        return (
            {
                "language": "rust",
                "analyzer": "clippy",
                "finding_count": count,
                "findings_per_kloc": _density(count, lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_severity": severity,
                        "count": observed,
                        "findings_per_kloc": _density(observed, lines),
                    }
                    for (rule, severity), observed in sorted(findings.items())
                ],
            },
            Status.OBSERVED if returncode in {0, 101} else Status.ERROR,
        )

    return parse


def _cython_lint_parser(lines: int) -> Parser:
    def parse(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any], Status]:
        findings: Counter[str] = Counter()
        for row in (stdout + stderr).splitlines():
            match = re.search(r":\d+:\d+:\s+([A-Z]+\d+)\b", row)
            if match:
                findings[match.group(1)] += 1
        count = sum(findings.values())
        return (
            {
                "language": "cython",
                "analyzer": "cython-lint",
                "finding_count": count,
                "findings_per_kloc": _density(count, lines),
                "rules": [
                    {
                        "rule": rule,
                        "native_severity": "UNSPECIFIED",
                        "count": observed,
                        "findings_per_kloc": _density(observed, lines),
                    }
                    for rule, observed in sorted(findings.items())
                ],
            },
            Status.OBSERVED,
        )

    return parse


def _run_native(
    *,
    environment: AnalyzerEnvironment,
    checkout: Path,
    project_id: str,
    snapshot_date: str,
    snapshot_commit: str | None,
    language: str,
    check_id: str,
    probe_id: str,
    command: list[str],
    parser: Parser,
    accepted: set[int],
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    force: bool,
) -> CheckResult:
    safe_probe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", probe_id)
    target = evidence_root / run_id / project_id / snapshot_date / check_id / safe_probe
    result_path = target / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    target.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = target / "stdout.txt", target / "stderr.txt"
    metadata_path = target / "metadata.json"
    started = datetime.now(UTC)
    clock = time.monotonic()
    observed: dict[str, Any] = {}
    status = Status.ERROR
    notes: str | None = None
    try:
        completed = analyzer_command(
            environment.root,
            command,
            source=checkout,
            work=target,
            config=config_root,
        )
        stdout = completed.stdout.decode(errors="replace")
        stderr = completed.stderr.decode(errors="replace")
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        observed, parsed_status = parser(stdout, stderr, completed.returncode)
        status = parsed_status if completed.returncode in accepted else Status.ERROR
        if status is Status.ERROR:
            notes = "Analyzer command failed; no project judgement was inferred."
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_bytes(exc.stdout or b"")
        stderr_path.write_bytes(exc.stderr or b"")
        observed = {"timed_out": True}
        status = Status.UNTESTABLE
        notes = "Analyzer exceeded its resource budget."
    except (OSError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        observed = {"audit_error": type(exc).__name__}
        notes = "Analyzer machinery failed; no project judgement was inferred."
    duration = time.monotonic() - clock
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "command": command,
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "duration_seconds": duration,
                "environment_id": environment.environment_id,
                "network": "none",
                **audit_code_identity(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = CheckResult(
        run_id=run_id,
        project_id=project_id,
        snapshot_date=snapshot_date,
        snapshot_commit=snapshot_commit,
        source_component_id=f"{language}:production",
        check_id=check_id,
        probe_id=probe_id,
        domain="source",
        status=status,
        result_kind=ResultKind.MEASUREMENT,
        method="automated_with_manifest",
        expected={"measurement_only": True, "network": "none"},
        observed=observed,
        tool=ToolIdentity(name=probe_id.split(":")[-1], version="pinned by analyzer lock"),
        command=command,
        started_at=started,
        duration_seconds=duration,
        environment_id=environment.environment_id,
        config_sha256=sha256_file(config_root / "rubric.yaml"),
        evidence=EvidencePaths(
            stdout=evidence_path(stdout_path, evidence_root),
            stderr=evidence_path(stderr_path, evidence_root),
            metadata=evidence_path(metadata_path, evidence_root),
        ),
        notes=notes,
    )
    result.write(result_path)
    return result


def run_non_python_native_analyzers(
    *,
    environment: AnalyzerEnvironment,
    manifest: dict[str, Any],
    checkout: Path,
    language: str,
    files: list[Path],
    run_id: str,
    evidence_root: Path,
    config_root: Path,
    snapshot_date: str,
    snapshot_commit: str | None,
    force: bool = False,
) -> list[CheckResult]:
    project_id = manifest["project"]["id"]
    relative = [f"/source/{path.relative_to(checkout).as_posix()}" for path in files]
    line_count = _lines(files)
    common = {
        "environment": environment,
        "checkout": checkout,
        "project_id": project_id,
        "snapshot_date": snapshot_date,
        "snapshot_commit": snapshot_commit,
        "language": language,
        "run_id": run_id,
        "evidence_root": evidence_root,
        "config_root": config_root,
        "force": force,
    }
    if language == "perl":
        lint = _run_native(
            **common,
            check_id="SRC-NATIVE-LINT-001",
            probe_id="perl:perlcritic",
            command=[
                "/workspace/perl5/bin/perlcritic",
                "--profile",
                "/config/perlcritic-standard.rc",
                "--verbose",
                "%p~|~%m~|~%s~|~%l~|~%c\\n",
                *relative,
            ],
            parser=_perlcritic_parser(line_count),
            accepted=set(range(0, 6)),
        )
        security = write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="SRC-NATIVE-SECURITY-001",
            probe_id="source:perl:security",
            domain="source",
            status=Status.NOT_APPLICABLE,
            observed={"language": "perl", "reason": "No frozen source-security analyzer."},
            evidence_root=evidence_root,
            config_path=config_root / "rubric.yaml",
            snapshot_date=snapshot_date,
            snapshot_commit=snapshot_commit,
            source_component_id="perl:production",
            tool=ToolIdentity(name="Seebot analyzer dispatcher", version=__version__),
            force=force,
        )
        return [lint, security]
    if language in {"c", "cpp"}:
        command = [
            "cppcheck",
            "--xml",
            "--xml-version=2",
            "--enable=warning,style,performance,portability",
            "-j",
            "2",
            *relative,
        ]
        lint = _run_native(
            **common,
            check_id="SRC-NATIVE-LINT-001",
            probe_id=f"{language}:cppcheck:lint",
            command=command,
            parser=_cppcheck_parser(line_count, security_only=False),
            accepted={0},
        )
        if lint.status is Status.OBSERVED:
            stdout_path = evidence_root.parent / lint.evidence.stdout
            stderr_path = evidence_root.parent / lint.evidence.stderr
            security_observed, security_status = _cppcheck_parser(line_count, security_only=True)(
                stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"),
                0,
            )
            security_observed["source_evidence"] = lint.evidence.stderr
        else:
            security_status = lint.status
            security_observed = {
                "analyzer": "cppcheck",
                "source_evidence": lint.evidence.stderr,
                "reason": "The shared cppcheck invocation did not complete.",
            }
        security = write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="SRC-NATIVE-SECURITY-001",
            probe_id=f"{language}:cppcheck:security",
            domain="source",
            status=security_status,
            observed=security_observed,
            evidence_root=evidence_root,
            config_path=config_root / "rubric.yaml",
            snapshot_date=snapshot_date,
            snapshot_commit=snapshot_commit,
            source_component_id=f"{language}:production",
            tool=ToolIdentity(name="cppcheck", version="2.21.0"),
            command=command,
            environment_identity=environment.environment_id,
            notes="Security-rule indicators are filtered from the same cppcheck XML evidence.",
            force=force,
        )
        return [lint, security]
    if language == "java":
        base = [
            "sh",
            "/workspace/.pixi/envs/default/bin/pmd",
            "check",
            "-d",
            ",".join(relative),
            "-f",
            "json",
            "-R",
        ]
        return [
            _run_native(
                **common,
                check_id="SRC-NATIVE-LINT-001",
                probe_id="java:pmd:lint",
                command=base
                + [
                    "category/java/bestpractices.xml,category/java/errorprone.xml,"
                    "category/java/design.xml"
                ],
                parser=_pmd_parser(line_count, language),
                accepted={0, 4},
            ),
            _run_native(
                **common,
                check_id="SRC-NATIVE-SECURITY-001",
                probe_id="java:pmd:security",
                command=base + ["category/java/security.xml"],
                parser=_pmd_parser(line_count, language),
                accepted={0, 4},
            ),
        ]
    if language == "rust":
        lint = _run_native(
            **common,
            check_id="SRC-NATIVE-LINT-001",
            probe_id="rust:clippy",
            command=["cargo", "clippy", "--locked", "--offline", "--message-format=json"],
            parser=_clippy_parser(line_count),
            accepted={0, 101},
        )
        security = write_measurement(
            project_id=project_id,
            run_id=run_id,
            check_id="SRC-NATIVE-SECURITY-001",
            probe_id="source:rust:security",
            domain="source",
            status=Status.NOT_APPLICABLE,
            observed={"language": "rust", "reason": "No frozen source-only security analyzer."},
            evidence_root=evidence_root,
            config_path=config_root / "rubric.yaml",
            snapshot_date=snapshot_date,
            snapshot_commit=snapshot_commit,
            source_component_id="rust:production",
            tool=ToolIdentity(name="Seebot analyzer dispatcher", version=__version__),
            force=force,
        )
        return [lint, security]
    if language == "cython":
        lint = _run_native(
            **common,
            check_id="SRC-NATIVE-LINT-001",
            probe_id="cython:cython-lint",
            command=["cython-lint", *relative],
            parser=_cython_lint_parser(line_count),
            accepted={0, 1},
        )
        return [
            lint,
            write_measurement(
                project_id=project_id,
                run_id=run_id,
                check_id="SRC-NATIVE-SECURITY-001",
                probe_id="source:cython:security",
                domain="source",
                status=Status.NOT_APPLICABLE,
                observed={
                    "language": "cython",
                    "reason": "No frozen source-security analyzer for the limited profile.",
                },
                evidence_root=evidence_root,
                config_path=config_root / "rubric.yaml",
                snapshot_date=snapshot_date,
                snapshot_commit=snapshot_commit,
                source_component_id="cython:production",
                tool=ToolIdentity(name="Seebot analyzer dispatcher", version=__version__),
                force=force,
            ),
        ]
    raise ValueError(f"Unsupported native analyzer language: {language}")
