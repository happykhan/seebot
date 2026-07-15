from pathlib import Path

from seebot.analyzers.structure import production_files, structural_facts


def test_production_inventory_ignores_test_source_entirely(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "tool.py").write_text(
        "def documented(a, b):\n"
        '    """Return a value."""\n'
        "    if a:\n"
        "        return b\n"
        "    return a\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_tool.py").write_text(
        "def test_tool():\n    assert True\n", encoding="utf-8"
    )
    manifest = {
        "source": {
            "language_roots": {"python": ["."]},
            "generated_paths": [],
            "vendored_paths": [],
            "excluded_paths": [],
        }
    }
    files, excluded = production_files(tmp_path, manifest, "python")
    assert [path.name for path in files] == ["tool.py"]
    assert excluded == [{"path": "tests/test_tool.py", "reason": "standard non-production path"}]

    facts = structural_facts(files, "python")
    assert facts["inventory"]["files"] == 1
    assert facts["functions"]["function_count"] == 1
    assert facts["complexity"]["maximum"] == 2
    assert facts["documentation"]["coverage_percent"] == 100.0


def test_explicit_reviewed_source_file_can_be_extensionless(tmp_path: Path) -> None:
    script = tmp_path / "any2fasta"
    script.write_text("#!/usr/bin/env perl\nsub main { return 0; }\n", encoding="utf-8")
    manifest = {
        "source": {
            "language_roots": {"perl": ["any2fasta"]},
            "generated_paths": [],
            "vendored_paths": [],
            "excluded_paths": [],
        }
    }

    files, excluded = production_files(tmp_path, manifest, "perl")

    assert files == [script]
    assert excluded == []
