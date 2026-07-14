"""Shared result models and conservative audit status semantics."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNTESTABLE = "UNTESTABLE"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"


class Applicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ToolIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class EvidencePaths(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stdout: str
    stderr: str
    metadata: str


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    run_id: str
    package_id: str
    check_id: str
    domain: str
    status: Status
    applicability: Applicability = Applicability.APPLICABLE
    method: str = "automated_with_manifest"
    expected: dict[str, Any] = Field(default_factory=dict)
    observed: dict[str, Any] = Field(default_factory=dict)
    tool: ToolIdentity
    command: list[str] | None
    started_at: datetime
    duration_seconds: float = Field(ge=0)
    environment_id: str
    config_sha256: str
    evidence: EvidencePaths
    notes: str | None = None

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
