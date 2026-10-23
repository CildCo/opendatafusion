from bench import config


def test_fixed_ports_and_paths():
    assert str(config.ROOT) == "/data/odf-bench" or config.ROOT.name == "odf-bench"
    assert (config.PG_PORT, config.PROXY_PORT) == (5433, 5434)
    assert (config.API_PORT, config.API2_PORT, config.MCP_PORT) == (18180, 18181, 18182)
    assert (config.HTTP_PORT, config.FAULT_PORT) == (18183, 18184)
    assert config.DB_CONTROL == "odf_bench"
    assert config.DB_SHOP == "shop"
    assert config.DB_MART == "mart"


def test_phase_budget_and_seed_are_stable():
    assert config.SEED == 20261022
    assert [p[0] for p in config.PHASES] == [
        "warmup", "baseline", "peak", "fault", "cooldown", "soak"]
    assert sum(p[1] for p in config.PHASES) == 240
    assert config.BUDGET["memory_gb"] == 26
