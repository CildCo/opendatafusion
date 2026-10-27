import httpx
import pytest

from odf.trino.client import TrinoClient, TrinoError, literal, render_params


def _client(handler):
    return TrinoClient(
        "http://trino", "odf",
        client=httpx.Client(base_url="http://trino",
                            transport=httpx.MockTransport(handler)))


def test_query_follows_next_uri_and_collects_rows():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.method == "POST":
            return httpx.Response(200, json={
                "id": "q1", "nextUri": "http://trino/v1/statement/q1/1",
                "columns": [{"name": "id"}, {"name": "name"}],
                "data": [[1, "alpha"]]})
        if str(request.url).endswith("/1"):
            return httpx.Response(200, json={
                "id": "q1", "nextUri": "http://trino/v1/statement/q1/2",
                "data": [[2, "beta"]]})
        return httpx.Response(200, json={"id": "q1"})

    out = _client(handler).query("select * from t")

    assert out["columns"] == ["id", "name"]
    assert out["rows"] == [{"id": 1, "name": "alpha"},
                           {"id": 2, "name": "beta"}]
    assert out["row_count"] == 2
    assert out["truncated"] is False
    assert len(seen) == 3


def test_query_reads_columns_from_a_later_page():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={
                "id": "q1", "nextUri": "http://trino/v1/statement/q1/1"})
        return httpx.Response(200, json={
            "id": "q1", "columns": [{"name": "n"}], "data": [[7]]})

    out = _client(handler).query("select 7 as n")
    assert out["columns"] == ["n"]
    assert out["rows"] == [{"n": 7}]


def test_query_error_in_200_body_raises():
    def handler(request):
        return httpx.Response(200, json={
            "error": {"message": "Table does not exist", "errorCode": 47}})

    with pytest.raises(TrinoError, match="Table does not exist"):
        _client(handler).query("select * from missing")


def test_query_truncates_at_max_rows():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={
                "id": "q1", "columns": [{"name": "n"}],
                "data": [[1], [2], [3]]})
        return httpx.Response(200, json={"id": "q1"})

    out = _client(handler).query("select n from t", max_rows=2)
    assert out["row_count"] == 2
    assert out["truncated"] is True
    assert out["rows"] == [{"n": 1}, {"n": 2}]


def test_post_sends_statement_and_headers():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.content.decode("utf-8")
        seen["user"] = request.headers.get("X-Trino-User")
        seen["catalog"] = request.headers.get("X-Trino-Catalog")
        seen["schema"] = request.headers.get("X-Trino-Schema")
        return httpx.Response(200, json={"id": "q1"})

    client = TrinoClient(
        "http://trino", "odf", catalog="iceberg", schema="demo",
        client=httpx.Client(
            base_url="http://trino",
            headers={"X-Trino-User": "odf", "X-Trino-Catalog": "iceberg",
                     "X-Trino-Schema": "demo"},
            transport=httpx.MockTransport(handler)))
    client.query("select 1")

    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/statement"
    assert seen["body"] == "select 1"
    assert seen["user"] == "odf"
    assert seen["catalog"] == "iceberg"
    assert seen["schema"] == "demo"


def test_from_dsn_parses_catalog_schema_and_https():
    c = TrinoClient.from_dsn("trino://odf:secret@trino:8080/iceberg/demo")
    assert c.catalog == "iceberg"
    assert c.schema == "demo"
    assert c.user == "odf"
    assert c.password == "secret"
    assert c.base_url == "http://trino:8080"

    secure = TrinoClient.from_dsn("trino+https://u@t:8443")
    assert secure.base_url == "https://t:8443"
    assert secure.catalog == ""
    assert secure.schema == ""


def test_from_dsn_defaults_port_and_user():
    c = TrinoClient.from_dsn("trino://trino")
    assert c.base_url == "http://trino:8080"
    assert c.user == "odf"


def test_from_dsn_rejects_other_schemes():
    with pytest.raises(ValueError):
        TrinoClient.from_dsn("postgresql://u@h/db")


def test_render_params_inlines_literals_and_escapes_quotes():
    sql = "select * from t where a = :a and b = :b and c = :c"
    out = render_params(sql, {"a": "it's", "b": 3, "c": None})
    assert out == "select * from t where a = 'it''s' and b = 3 and c = NULL"


def test_render_params_leaves_casts_and_empty_params():
    assert render_params("select x::int from t", {}) == "select x::int from t"
    assert render_params("select x::int, :v", {"v": 1}) == \
        "select x::int, 1"


def test_render_params_rejects_missing_name():
    with pytest.raises(ValueError, match="missing parameter"):
        render_params("select :nope", {})


def test_literal_renders_scalars():
    from datetime import date, datetime, timezone

    assert literal(True) == "TRUE"
    assert literal(False) == "FALSE"
    assert literal(1.5) == "1.5"
    assert literal("a'b") == "'a''b'"
    assert literal(date(2026, 1, 2)) == "'2026-01-02'"
    assert literal(datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)) == \
        "'2026-01-02T03:04:00+00:00'"
    assert literal([1, "a"]) == "ARRAY[1, 'a']"


def test_literal_refuses_unknown_types():
    with pytest.raises(ValueError):
        literal(object())


def test_literal_refuses_non_finite_numbers():
    with pytest.raises(ValueError):
        literal(float("inf"))


def test_ping_reports_false_on_error():
    def handler(request):
        return httpx.Response(200, json={"error": {"message": "boom"}})

    assert _client(handler).ping() is False


def test_ping_reports_true_on_success():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={
                "id": "q1", "columns": [{"name": "_col0"}], "data": [[1]]})
        return httpx.Response(200, json={"id": "q1"})

    assert _client(handler).ping() is True
