import pytest

from odf.connectors.registry import (build_dsn, catalog, capabilities,
                                     get_spec, masked_config, parse_dsn,
                                     require_spec, supports)


def test_catalog_covers_every_console_type():
    rows = catalog()
    kinds = {row["kind"] for row in rows["connectors"]}
    assert kinds == {"postgres", "mysql", "mariadb", "sqlite", "oracle",
                     "mssql", "clickhouse", "trino", "file", "http", "es"}
    for row in rows["connectors"]:
        assert row["capabilities"]["test"] is True
        assert row["fields"]


def test_http_and_es_declare_honest_capabilities():
    http = capabilities("http")
    assert http["metadata"] is False and http["query"] is False
    assert http["source"] and http["sink"]
    es = capabilities("es")
    assert es["metadata"] is True and es["query"] is False
    assert es["source"] and es["sink"]


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError):
        require_spec("not-a-database")
    assert get_spec("not-a-database") is None
    assert supports("not-a-database", "test") is False


def test_postgres_dsn_roundtrip_keeps_special_passwords():
    values = {"host": "db.internal", "port": 5432, "database": "sales",
              "username": "odf", "password": "p@ss:w/rd",
              "sslmode": "require"}
    dsn = build_dsn("postgres", values)
    assert "postgresql+psycopg://" in dsn
    assert "sslmode=require" in dsn
    parsed = parse_dsn("postgres", dsn)
    assert parsed["password"] == "p@ss:w/rd"
    assert parsed["database"] == "sales"
    assert parsed["sslmode"] == "require"


def test_sqlite_file_and_api_dsn_roundtrip():
    assert build_dsn("sqlite", {"path": "sqlite:////data/app.db"}) == \
        "sqlite:////data/app.db"
    assert parse_dsn("sqlite", "sqlite:////data/app.db")["path"] == \
        "/data/app.db"
    assert build_dsn("file", {"path": "/data/odf/files/a.csv"}) == \
        "/data/odf/files/a.csv"
    assert parse_dsn("http", "https://api.example.com")["url"] == \
        "https://api.example.com"
    assert parse_dsn("es", "http://es:9200")["url"] == "http://es:9200"


def test_trino_clickhouse_and_oracle_roundtrip():
    trino = build_dsn("trino", {"host": "trino", "port": 8080,
                                "catalog": "iceberg", "schema": "sales",
                                "username": "odf", "password": "secret"})
    assert trino.startswith("trino://")
    parsed = parse_dsn("trino", trino)
    assert parsed["catalog"] == "iceberg"
    assert parsed["schema"] == "sales"
    assert parsed["password"] == "secret"
    secure = build_dsn("trino", {"host": "trino", "port": 8443,
                                 "catalog": "iceberg", "username": "odf",
                                 "secure": "true"})
    assert secure.startswith("trino+https://")
    click = build_dsn("clickhouse", {"host": "ch", "port": 8443,
                                     "database": "default",
                                     "username": "default",
                                     "password": "pw", "secure": "true"})
    assert click.startswith("clickhouse+https://")
    back = parse_dsn("clickhouse", click)
    assert back["secure"] == "true" and back["password"] == "pw"
    oracle = build_dsn("oracle", {"host": "ora", "port": 1521,
                                  "service": "ORCLPDB1", "username": "odf",
                                  "password": "pw"})
    back = parse_dsn("oracle", oracle)
    assert back["service"] == "ORCLPDB1" and back["password"] == "pw"


def test_required_fields_and_masking():
    with pytest.raises(ValueError):
        build_dsn("postgres", {"host": "db", "username": "u"})
    masked = masked_config("postgres",
                           build_dsn("postgres", {
                               "host": "db", "database": "d",
                               "username": "u", "password": "secret"}))
    assert masked["password"] == ""
    assert masked["has_password"] is True
    assert "secret" not in str(masked)
