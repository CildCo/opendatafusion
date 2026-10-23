from bench.generate import shop


def test_small_generation_row_counts(tmp_path):
    paths = shop.generate(tmp_path, scale=0.0001)
    assert set(paths) == {"customers", "products", "orders",
                          "order_items", "payments", "refunds", "events"}
    import duckdb
    for table, path in paths.items():
        n = duckdb.sql(
            f"select count(*) from read_parquet('{path.as_posix()}')").fetchone()[0]
        assert n == max(1, round(shop.ROW_COUNTS[table] * 0.0001))
