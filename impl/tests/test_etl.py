from odf.workers.etl import build_select


def test_select_has_cursor_filter():
    sql, params = build_select("public.t", "updated_at",
                               "2026-01-01T00:00:00Z", 100)
    assert "updated_at >" in sql and params["limit"] == 100
