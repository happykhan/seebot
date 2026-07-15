"""Shared writer for non-command observations with portable evidence paths."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seebot.evidence import audit_code_identity, environment_id, evidence_path, sha256_file
from seebot.models import (
    Applicability,
    CheckResult,
    EvidencePaths,
    ResultKind,
    Status,
    ToolIdentity,
)


def write_measurement(
    *,
    project_id: str,
    run_id: str,
    check_id: str,
    probe_id: str,
    domain: str,
    status: Status,
    observed: dict[str, Any],
    evidence_root: Path,
    config_path: Path,
    snapshot_date: str,
    snapshot_commit: str | None,
    tool: ToolIdentity,
    repository_id: str | None = None,
    source_component_id: str | None = None,
    executable_id: str | None = None,
    installation_id: str | None = None,
    result_kind: ResultKind = ResultKind.MEASUREMENT,
    applicability: Applicability = Applicability.APPLICABLE,
    method: str = "automated_with_manifest",
    expected: dict[str, Any] | None = None,
    command: list[str] | None = None,
    environment_identity: str | None = None,
    notes: str | None = None,
    force: bool = False,
) -> CheckResult:
    safe_probe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", probe_id)
    target = evidence_root / run_id / project_id / snapshot_date / check_id / safe_probe
    result_path = target / "result.json"
    if result_path.exists() and not force:
        return CheckResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    target.mkdir(parents=True, exist_ok=True)
    stdout_path = target / "observation.json"
    stderr_path = target / "stderr.txt"
    metadata_path = target / "metadata.json"
    started = datetime.now(UTC)
    stdout_path.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    identity = environment_identity or environment_id()
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "environment_id": identity,
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
        repository_id=repository_id,
        snapshot_date=snapshot_date,
        snapshot_commit=snapshot_commit,
        source_component_id=source_component_id,
        executable_id=executable_id,
        installation_id=installation_id,
        check_id=check_id,
        probe_id=probe_id,
        domain=domain,
        status=status,
        result_kind=result_kind,
        applicability=applicability,
        method=method,
        expected=expected or {"measurement_only": True},
        observed=observed,
        tool=tool,
        command=command,
        started_at=started,
        duration_seconds=0,
        environment_id=identity,
        config_sha256=sha256_file(config_path),
        evidence=EvidencePaths(
            stdout=evidence_path(stdout_path, evidence_root),
            stderr=evidence_path(stderr_path, evidence_root),
            metadata=evidence_path(metadata_path, evidence_root),
        ),
        notes=notes,
    )
    result.write(result_path)
    return result
