"""Component-first representation of Bioconda recipe test depth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeTestFacts:
    has_import_test: bool = False
    has_help_test: bool = False
    has_version_test: bool = False
    has_command_test: bool = False
    uses_test_data: bool = False
    runs_analysis: bool = False
    asserts_output_exists: bool = False
    asserts_output_content: bool = False
    asserts_output_format: bool = False

    @property
    def suggested_depth(self) -> int:
        """Suggest the ordinal level while preserving facts for review."""
        if self.runs_analysis and (self.asserts_output_content or self.asserts_output_format):
            return 4
        if self.runs_analysis and self.uses_test_data:
            return 3
        if self.runs_analysis or (self.has_command_test and self.uses_test_data):
            return 2
        if any(
            (
                self.has_import_test,
                self.has_help_test,
                self.has_version_test,
                self.has_command_test,
            )
        ):
            return 1
        return 0
