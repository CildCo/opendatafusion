"""Live recovery checks that need a running bench stack."""
import json
import time
from pathlib import Path

import psycopg

from bench import config, pg
from bench.faults import inject
from bench.seed import seed_platform


def _pipeline(admin, name, shop_ds, mart_ds, source, sink, cursor,
              batch=200000):
    content = {
        "nodes": [
            {"id": "src", "type": "source",
             "config": {"datasource_id": shop_ds, "table": source,
                        "pk": "id", "cursor_column": cursor}},
            {"id": "dst", "type": "sink",
             "config": {"datasource_id": mart_ds, "table": sink,
                        "pk": ["id"], "mode": "upsert"}}],
        "edges": [{"from": "src", "to": "dst"}],
        "settings": {"batch": batch},
    }
    aid = admin.post("/pipelines", json={
        "project_id": 1, "name": name, "content": content})["id"]
    admin.publish("publish_pipeline", aid, 1)
    return aid


def _run(admin, aid, timeout=1500):
    job = admin.post(f"/pipelines/{aid}/run", json={})["job_id"]
    started = time.time()
    while time.time() - started < timeout:
        rows = admin.get(f"/pipelines/{aid}/jobs")
        row = next((x for x in rows if x["id"] == job), None)
        if row and row["status"] in ("success", "failed"):
            return {"status": row["status"],
                    "seconds": round(time.time() - started, 1),
                    "error": row.get("last_error")}
        time.sleep(2)
    return {"status": "timeout"}


def in_flight_kill(admin, shop_ds, mart_ds):
    with psycopg.connect(pg.dsn("mart").replace(
            "postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute("drop table if exists orders_copy")
        conn.execute("""create table orders_copy (
            id bigint primary key, customer_id bigint, order_no text,
            status text, channel text, province text, city text,
            amount numeric(12,2), discount numeric(12,2),
            created_at timestamptz, updated_at timestamptz)""")
    aid = _pipeline(admin, "recovery-orders", shop_ds, mart_ds,
                    "orders", "orders_copy", "id")
    job = admin.post(f"/pipelines/{aid}/run", json={})["job_id"]
    time.sleep(15)
    killed = inject.kill_worker(config.ROOT)
    time.sleep(2)
    started_worker = inject.start_worker(config.ROOT)
    result = _run(admin, aid, timeout=1500)
    with psycopg.connect(pg.dsn("mart").replace(
            "postgresql+psycopg://", "postgresql://")) as conn:
        count = conn.execute("select count(*) from orders_copy").fetchone()[0]
    return {"job_id": job, "killed": killed,
            "started_worker": started_worker, **result, "rows": count}


def cursor_ties(admin, shop_ds, mart_ds):
    with psycopg.connect(pg.dsn("shop").replace(
            "postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute("drop table if exists tie_src")
        conn.execute("""create table tie_src (
            id bigint primary key, updated_at timestamptz, v text)""")
        with conn.cursor() as cur:
            cur.executemany(
                "insert into tie_src values (%s, %s, %s)",
                [(i, f"2025-01-01 00:{i // 100:02d}:00+08", f"v{i}")
                 for i in range(1, 1001)])
    with psycopg.connect(pg.dsn("mart").replace(
            "postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute("drop table if exists tie_dst")
        conn.execute("""create table tie_dst (
            id bigint primary key, updated_at timestamptz, v text)""")
    aid = _pipeline(admin, "cursor-ties", shop_ds, mart_ds,
                    "tie_src", "tie_dst", "updated_at", batch=100)
    first = _run(admin, aid)
    second = _run(admin, aid)
    with psycopg.connect(pg.dsn("mart").replace(
            "postgresql+psycopg://", "postgresql://")) as conn:
        count = conn.execute("select count(*) from tie_dst").fetchone()[0]
    return {"first": first, "second": second, "rows": count}


def main():
    base = f"http://127.0.0.1:{config.API_PORT}"
    admin = seed_platform.Client(base, "acceptance", "AcceptPassw0rd!")
    admin.login()
    by_name = {d["name"]: d["id"] for d in admin.get("/datasources")}
    out = {
        "in_flight_kill": in_flight_kill(
            admin, by_name["shop"], by_name["mart"]),
        "cursor_ties": cursor_ties(
            admin, by_name["shop"], by_name["mart"]),
    }
    Path(config.ROOT / "report").mkdir(parents=True, exist_ok=True)
    (config.ROOT / "report" / "recovery.json").write_text(
        json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
