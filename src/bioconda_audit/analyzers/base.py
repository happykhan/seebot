"""Contracts for analyzers that return observations rather than judgements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AnalyzerObservation:
    metric: str
    value: int | float | str | bool | None
    unit: str | None
    source_root: Path


class Analyzer(Protocol):
    name: str
    version: str

    def run(self, source_root: Path) -> list[AnalyzerObservation]: ...
