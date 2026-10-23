from bench import pg


def test_conf_contains_bench_tuning():
    text = "\n".join(pg.conf_lines())
    assert "shared_buffers = 8GB" in text
    assert "work_mem = 32MB" in text
    assert "max_connections = 200" in text
    assert "track_io_timing = on" in text
    assert "port = 5433" in text


def test_dsn_is_local_trust_connection():
    assert pg.dsn("shop") == (
        "postgresql+psycopg://odf@127.0.0.1:5433/shop")
