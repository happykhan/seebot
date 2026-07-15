from pathlib import Path

from seebot.storage import directory_size, prune_owned_directory


def test_owned_cache_pruning_is_scoped(tmp_path: Path) -> None:
    cache = tmp_path / ".seebot-cache"
    cache.mkdir()
    (cache / "data").write_bytes(b"123")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "keep").write_text("keep", encoding="utf-8")
    assert directory_size(cache) == 3
    assert prune_owned_directory(cache) == 3
    assert not cache.exists()
    assert unrelated.exists()
