from odf.services import connections


def test_engine_for_dsn_keeps_the_password(monkeypatch):
    captured = {}

    class FakeEngine:
        def dispose(self):
            pass

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeEngine()

    monkeypatch.setattr(connections, "create_engine", fake_create_engine)
    with connections.engine_for_dsn(
            "postgresql+psycopg://odf:s3cret@db.example:5432/warehouse",
            "postgres"):
        pass
    assert "s3cret" in captured["url"]
    assert "***" not in captured["url"]
