import io
import tarfile
from pathlib import Path

import pytest

from seebot.source.fetch import extract_safe
from seebot.source.inventory import inventory_tree


def test_safe_tar_extracts(tmp_path: Path) -> None:
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("project/main.py")
        content = b"print('ok')\n"
        info.size = len(content)
        handle.addfile(info, io.BytesIO(content))
    target = tmp_path / "source"
    extract_safe(archive, target)
    assert (target / "project" / "main.py").read_bytes() == content


def test_tar_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as handle:
        info = tarfile.TarInfo("../escape.txt")
        content = b"escape"
        info.size = len(content)
        handle.addfile(info, io.BytesIO(content))
    with pytest.raises(ValueError, match="Unsafe archive member"):
        extract_safe(archive, tmp_path / "source")


def test_inventory_is_sorted_and_honours_exclusions(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "src" / "b.py").write_text("b")
    (tmp_path / "src" / "a.py").write_text("a")
    (tmp_path / "vendor" / "lib.py").write_text("vendor")
    rows = inventory_tree(tmp_path, [Path("vendor")])
    assert [row["path"] for row in rows] == ["src/a.py", "src/b.py"]


def test_inventory_classifies_languages_and_reviewed_roles(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() {}\n")
    (tmp_path / "tests" / "check.py").write_text("assert True\n")
    rows = inventory_tree(tmp_path, test_paths=[Path("tests")])
    indexed = {row["path"]: row for row in rows}
    assert indexed["src/main.rs"]["language"] == "rust"
    assert indexed["src/main.rs"]["source_role"] == "production"
    assert indexed["tests/check.py"]["language"] == "python"
    assert indexed["tests/check.py"]["source_role"] == "test"
