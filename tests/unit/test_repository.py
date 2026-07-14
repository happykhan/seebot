from bioconda_audit.analyzers.repository import repository_facts


def test_repository_facts_are_presence_observations() -> None:
    facts = repository_facts(
        [
            ".github/workflows/test.yml",
            "CITATION.cff",
            "CONTRIBUTING.rst",
            "LICENSE",
            "doc/index.rst",
            "src/tool.py",
            "tests/test_cli.py",
        ]
    )
    assert facts == {
        "file_count": 7,
        "licence_file_present": True,
        "contribution_guide_present": True,
        "citation_metadata_present": True,
        "ci_workflow_present": True,
        "test_path_present": True,
        "documentation_path_present": True,
    }
