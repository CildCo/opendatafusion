import argparse
import asyncio
import threading
import time

from bench import config, guard, pg, report
from bench.assertions import checks
from bench.generate import schema, shop
from bench.load import driver
from bench.seed import seed_platform


def phases(profile: str):
    if profile == "smoke":
        return [("warmup", 1, 5), ("smoke", 1, 5)]
    if profile == "targeted":
        return [("warmup", 3, 10), ("mixed", 15, 50), ("fault", 5, 30)]
    return config.PHASES


def _ids(admin) -> dict:
    def first(path):
        rows = admin.get(path)
        return rows[0]["id"] if rows else None
    return {"dataset": first("/datasets"), "metric": first("/metrics"),
            "dashboard": first("/dashboards")}


def _dsns():
    return {
        "shop": ("shop", pg.dsn("shop").replace(":5433", ":5434"), "postgres"),
        "mart": ("mart", pg.dsn("mart").replace(":5433", ":5434"), "postgres"),
        "sqlite": ("edge", str(config.ROOT / "edge.db"), "sqlite"),
        "csv": ("customers-csv",
                str(config.ROOT / "files" / "customers_1m.csv"), "file"),
        "parquet": ("events-parquet",
                    str(config.ROOT / "files" / "events_2025_09.parquet"), "file"),
        "http": ("mock-http", f"http://127.0.0.1:{config.HTTP_PORT}", "http"),
    }


def main(profile: str = "full") -> int:
    base = f"http://127.0.0.1:{config.API_PORT}"
    admin = seed_platform.Client(base, "acceptance", "AcceptPassw0rd!")
    admin.login()
    seeded = seed_platform.seed(base, {})
    codes = ["default"] + seed_platform.PROJECTS[:9]
    schema.create_mart(pg.dsn("mart"), codes)
    for code, meta in seeded["projects"].items():
        project_admin = seed_platform.Client(
            base, f"{code}-admin", "AdminPassw0rd!")
        project_admin.login(meta["project_id"])
        ds = seed_platform.seed_datasources(project_admin, _dsns())
        project_admin.post(f"/datasources/{ds['shop']}/sync")
        seed_platform.seed_assets(
            project_admin, ds, {code: meta["project_id"]})
    ids = _ids(admin)
    stop_event = threading.Event()
    guard.start(stop_event)
    results = {"profile": profile, "load": {}, "checks": [],
               "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    pipeline_runs = []
    pipelines = [] if profile == "targeted" else admin.get("/pipelines")[:2]
    for p in pipelines:
        job = admin.post(f"/pipelines/{p['id']}/run", json={})["job_id"]
        started = time.time()
        while time.time() - started < 900:
            rows = admin.get(f"/pipelines/{p['id']}/jobs")
            row = next((x for x in rows if x["id"] == job), None)
            if row and row["status"] in ("success", "failed"):
                pipeline_runs.append({
                    "pipeline_id": p["id"], "status": row["status"],
                    "seconds": round(time.time() - started, 1)})
                break
            time.sleep(2)
    results["pipelines"] = pipeline_runs
    for name, minutes, users in phases(profile):
        results["load"][name] = asyncio.run(
            driver.run(base, seeded["admin_token"], users, minutes * 60,
                       ids=ids, stop_event=stop_event))
    if stop_event.is_set():
        results["checks"].append(
            "runtime guard: " + ", ".join(guard.LAST_ERRORS))
    expected = shop.ROW_COUNTS["orders"]
    actual = checks.table_count(pg.dsn("shop"), "orders")
    if profile == "targeted":
        results["checks"] += checks.compare_counts(
            {"orders": expected}, {"orders": actual})
    else:
        result_orders = checks.table_count(
            pg.dsn("mart"), "orders_clean_default_orders")
        result_items = checks.table_count(
            pg.dsn("mart"), "orders_clean_default_items")
        results["checks"] += checks.compare_counts(
            {"orders": expected, "orders_sink": expected,
             "items_sink": expected},
            {"orders": actual, "orders_sink": result_orders,
             "items_sink": result_items})
    out = report.build(results)
    config.ROOT.joinpath("report").mkdir(parents=True, exist_ok=True)
    report.write(out, config.ROOT / "report" / "report.json")
    print(report.markdown(out))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="full", choices=("smoke", "targeted", "full"))
    args = parser.parse_args()
    raise SystemExit(main(args.profile))
