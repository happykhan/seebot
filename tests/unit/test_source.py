import io
import tarfile
from pathlib import Path

import pytest

from bioconda_audit.source.fetch import extract_safe
from bioconda_audit.source.inventory import inventory_tree


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
