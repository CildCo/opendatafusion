import json

from bench.faults import proxy


def test_mode_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(proxy, "MODE_FILE", tmp_path / "mode.json")
    proxy.set_mode(delay_ms=200, fail=False)
    assert json.loads((tmp_path / "mode.json").read_text()) == {
        "delay_ms": 200, "fail": False}
    assert proxy.read_mode()["delay_ms"] == 200
