from pathlib import Path

import duckdb


def build(root: Path) -> dict[str, int]:
    root = Path(root)
    files = root / "files"
    files.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute("SET memory_limit='4GB'")
    events = (root / "parquet" / "shop" / "events.parquet").as_posix()
    orders = (root / "parquet" / "shop" / "orders.parquet").as_posix()
    customers = (root / "parquet" / "shop" / "customers.parquet").as_posix()

    con.execute(f"""COPY (
        SELECT * FROM read_parquet('{events}')
        WHERE ts >= TIMESTAMP '2025-09-01' AND ts < TIMESTAMP '2025-10-01'
    ) TO '{(files / 'events_2025_09.parquet').as_posix()}'
      (FORMAT PARQUET, COMPRESSION ZSTD)""")
    con.execute(f"""COPY (SELECT * FROM read_parquet('{orders}') LIMIT 2000000)
        TO '{(files / 'orders_snapshot.parquet').as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)""")
    con.execute(f"""COPY (SELECT * FROM read_parquet('{customers}') LIMIT 1000000)
        TO '{(files / 'customers_1m.csv').as_posix()}' (FORMAT CSV, HEADER)""")
    con.execute(f"""COPY (SELECT * FROM read_parquet('{events}') LIMIT 1000000)
        TO '{(files / 'events_sample.jsonl').as_posix()}' (FORMAT JSON)""")
    counts = {
        "events_2025_09": con.sql(
            f"select count(*) from read_parquet('{(files / 'events_2025_09.parquet').as_posix()}')").fetchone()[0],
        "orders_snapshot": con.sql(
            f"select count(*) from read_parquet('{(files / 'orders_snapshot.parquet').as_posix()}')").fetchone()[0],
        "customers_1m": con.sql(
            f"select count(*) from read_csv_auto('{(files / 'customers_1m.csv').as_posix()}')").fetchone()[0],
        "events_sample": con.sql(
            f"select count(*) from read_json_auto('{(files / 'events_sample.jsonl').as_posix()}')").fetchone()[0],
    }
    con.close()
    return counts
