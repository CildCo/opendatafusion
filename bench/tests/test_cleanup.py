import pytest

from bench import cleanup


def test_cleanup_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup, "ROOT", tmp_path / "bench")
    root = tmp_path / "bench"
    root.mkdir()
    (root / cleanup.MARKER).write_text("bench")
    (root / "marker").write_text("x")
    first = cleanup.cleanup(root)
    second = cleanup.cleanup(root)
    assert first["removed"] is True
    assert second["removed"] is False


def test_cleanup_refuses_unmarked_directory(tmp_path):
    root = tmp_path / "not-bench"
    root.mkdir()
    (root / "important").write_text("keep")
    with pytest.raises(ValueError, match="missing"):
        cleanup.cleanup(root)
    assert (root / "important").exists()
