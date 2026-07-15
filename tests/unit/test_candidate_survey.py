from seebot.cohort.survey import (
    GITHUB_PATTERN,
    _artifact_at_cutoff,
    _classify_interface,
    _configuration_executables,
    _format_families,
    _repository_url,
)


def test_repository_mapping_uses_explicit_package_metadata() -> None:
    url, source = _repository_url({"home": "https://github.com/samtools/samtools", "dev_url": None})
    assert url == "https://github.com/samtools/samtools"
    assert source == "anaconda:home"
    assert _repository_url({"home": "https://example.org/tool"}) == (None, None)


def test_artifact_selection_respects_snapshot_cutoff() -> None:
    payload = {
        "files": [
            {
                "upload_time": "2026-06-30T12:00:00+00:00",
                "version": "1.0",
                "attrs": {"subdir": "linux-64"},
            },
            {
                "upload_time": "2026-07-02T12:00:00+00:00",
                "version": "2.0",
                "attrs": {"subdir": "linux-64"},
            },
        ]
    }
    assert _artifact_at_cutoff(payload)["version"] == "1.0"


def test_artifact_selection_prefers_latest_release_not_latest_rebuild() -> None:
    payload = {
        "files": [
            {
                "upload_time": "2026-04-25T12:00:00+00:00",
                "version": "0.1.19",
                "attrs": {"subdir": "linux-64"},
            },
            {
                "upload_time": "2026-03-18T12:00:00+00:00",
                "version": "1.23.1",
                "attrs": {"subdir": "linux-64"},
            },
        ]
    }
    assert _artifact_at_cutoff(payload)["version"] == "1.23.1"


def test_format_survey_keeps_unknown_explicit() -> None:
    assert _format_families("General utility") == ("UNKNOWN", "UNKNOWN")
    inputs, outputs = _format_families("Trim sequencing reads in FASTQ and make plots")
    assert "FASTQ" in inputs
    assert "report/plot" in outputs


def test_github_mapping_cannot_consume_template_newlines() -> None:
    match = GITHUB_PATTERN.search("https://github.com/example/tool\n{% set version = '1' %}")
    assert match is not None
    assert match.groups() == ("example", "tool")


def test_python_console_script_is_explicit_cli_evidence() -> None:
    text = '[project]\nname = "example"\n[project.scripts]\nexample = "example:main"\n'
    assert _configuration_executables("pyproject.toml", text) == ["example"]
    status, executables, evidence, exclusion = _classify_interface(
        package_name="example",
        summary="Example scientific program",
        primary_language="Python",
        tree_paths=["pyproject.toml"],
        configs={"pyproject.toml": text},
        readme="",
        recipe_text=None,
    )
    assert status == "confirmed_end_user_cli"
    assert executables == ["example"]
    assert evidence == ["repository:pyproject.toml:declared-executable:example"]
    assert exclusion is None


def test_documented_library_without_cli_is_excluded() -> None:
    status, executables, _, exclusion = _classify_interface(
        package_name="perl-example",
        summary="A Perl module and library for parsing examples",
        primary_language="Perl",
        tree_paths=["lib/Example.pm"],
        configs={},
        readme="# Example\nA Perl module.",
        recipe_text=None,
    )
    assert status == "excluded"
    assert executables == []
    assert exclusion == "LIBRARY_ONLY"
