import io
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import psycopg

from bench.generate import schema

COLUMNS = {
    "customers": ["id", "name", "phone", "email", "province", "city",
                  "address", "register_at", "vip_level", "status"],
    "products": ["id", "name", "category", "price", "cost", "status",
                 "created_at"],
    "orders": ["id", "customer_id", "order_no", "status", "channel",
               "province", "city", "amount", "discount", "created_at",
               "updated_at"],
    "order_items": ["id", "order_id", "product_id", "quantity",
                    "unit_price", "amount", "discount"],
    "payments": ["id", "order_id", "method", "amount", "status", "paid_at",
                 "transaction_no", "failure_reason"],
    "refunds": ["id", "order_id", "payment_id", "amount", "reason", "status",
                "created_at"],
    "events": ["id", "event_id", "user_id", "session_id", "event_type",
               "page", "product_id", "ts", "properties", "ip", "user_agent"],
}


def batch_to_csv(batch) -> bytes:
    if "properties" in batch.schema.names:
        idx = batch.schema.get_field_index("properties")
        batch = batch.set_column(
            idx, "properties", batch.column(idx).cast(pa.string()))
    sink = io.BytesIO()
    pacsv.write_csv(batch, sink, write_options=pacsv.WriteOptions(
        include_header=False, quoting_style="needed"))
    return sink.getvalue()


def copy_parquet(path: Path, dsn: str, table: str,
                 columns: list[str]) -> int:
    target = "events_raw" if table == "events" else table
    count = 0
    with psycopg.connect(schema._pg_dsn(dsn)) as conn:
        with conn.cursor() as cur:
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(batch_size=100_000):
                raw = batch_to_csv(batch)
                with cur.copy(
                        f"COPY {target} ({', '.join(columns)}) "
                        "FROM STDIN WITH (FORMAT CSV)") as copy:
                    copy.write(raw.decode("utf-8"))
                count += batch.num_rows
        conn.commit()
    return count


def load_all(root: Path, shop_dsn: str) -> dict[str, int]:
    schema.create_schema(shop_dsn)
    counts = {}
    for table, columns in COLUMNS.items():
        counts[table] = copy_parquet(
            Path(root) / "parquet" / "shop" / f"{table}.parquet",
            shop_dsn, table, columns)
    schema.create_indexes(shop_dsn)
    return counts
