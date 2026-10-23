from bench import setup_env


def test_build_env_contains_three_databases(tmp_path):
    text = setup_env.build_env_text(
        "postgresql+psycopg://odf@127.0.0.1:5433/odf_bench",
        "postgresql+psycopg://odf@127.0.0.1:5434/shop",
        "postgresql+psycopg://odf@127.0.0.1:5434/mart",
        "j" * 32, "k" * 44)
    assert "odf_bench" in text and "/shop" in text and "/mart" in text
    assert "ODF_MCP_PORT=18182" in text
