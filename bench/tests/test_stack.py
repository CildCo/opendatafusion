from bench import stack


def test_env_file_has_fixed_ports_and_pool():
    lines = stack.env_lines(
        "postgresql+psycopg://odf@127.0.0.1:5433/odf_bench",
        "postgresql+psycopg://odf@127.0.0.1:5434/shop",
        "postgresql+psycopg://odf@127.0.0.1:5434/mart",
        "j" * 32, "k" * 44)
    text = "\n".join(lines)
    assert "ODF_DATABASE_URL=postgresql+psycopg://odf@127.0.0.1:5433/odf_bench" in text
    assert "ODF_MCP_PORT=18182" in text
    assert "ODF_DB_POOL_SIZE=20" in text
    assert "ODF_DB_MAX_OVERFLOW=40" in text
    assert "ODF_WEBHOOK_ALLOW_PRIVATE=true" in text


def test_command_lines_are_fixed():
    commands = stack.command_lines("/data/odf-bench", "/data/odf-bench/app")
    assert any("--port 18180" in c for c in commands)
    assert any("--port 18181" in c for c in commands)
    assert any("odf.worker" in c for c in commands)
    assert any("odf.scheduler" in c for c in commands)
