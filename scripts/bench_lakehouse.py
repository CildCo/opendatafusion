"""GB-scale lakehouse benchmark driven through the platform API.

    ODF_API=http://127.0.0.1:18080 ODF_USER=admin ODF_PASSWORD=... \
    LAKE_DSN='trino://odf@<trino-host>:8080/iceberg/odf_bench' \
    SPARK_ARTIFACT=local:///opt/odf-spark-jars/bench_ingest.py \
    BENCH_TABLE=iceberg.odf_bench.events BENCH_ROWS=30000000 \
    python scripts/bench_lakehouse.py

The Spark job inherits the lakehouse profile from the control plane, so no
catalog configuration is passed here.
"""

import os
import sys
import time

import httpx

API = os.environ.get("ODF_API", "http://127.0.0.1:18080").rstrip("/")
USER = os.environ.get("ODF_USER", "admin")
PASSWORD = os.environ.get("ODF_PASSWORD", "")
LAKE_DSN = os.environ.get(
    "LAKE_DSN", "trino://odf@127.0.0.1:8080/iceberg/odf_bench")
ARTIFACT = os.environ.get(
    "SPARK_ARTIFACT", "local:///opt/odf-spark-jars/bench_ingest.py")
ROWS = int(os.environ.get("BENCH_ROWS", "10000000"))
TARGET = os.environ.get("BENCH_TABLE", "iceberg.odf_bench.events")
WAIT_S = int(os.environ.get("WAIT_S", "3600"))
EXECUTORS = int(os.environ.get("EXECUTORS", "3"))

SPEC = {
    "main_application_file": ARTIFACT,
    "args": [TARGET, str(ROWS), "32",
             os.environ.get("BENCH_RESET", "1")],
    "driver_cores": 2,
    "driver_memory": "2g",
    "executor_cores": 2,
    "executor_instances": EXECUTORS,
    "executor_memory": "3g",
}

QUERIES = [
    ("count", "SELECT count(*) AS n FROM %s"),
    ("by_city", "SELECT city, count(*) AS n, sum(amount) AS total "
                "FROM %s GROUP BY city ORDER BY n DESC"),
    ("by_day", "SELECT date_trunc('day', event_ts) AS day, count(*) AS n "
               "FROM %s GROUP BY 1 ORDER BY 1"),
    ("top_users", "SELECT user_id, count(*) AS n, sum(amount) AS total "
                  "FROM %s GROUP BY user_id ORDER BY n DESC LIMIT 20"),
    ("size", None),
]


def main():
    http = httpx.Client(base_url=API, timeout=300.0)
    login = http.post("/api/v1/auth/login", json={
        "username": USER, "password": PASSWORD, "project_id": 1})
    login.raise_for_status()
    http.headers["Authorization"] = "Bearer " + login.json()["token"]

    datasources = http.get("/api/v1/datasources").json()
    lake = next((d for d in datasources if d["kind"] == "trino"), None)
    if not lake:
        created = http.post("/api/v1/datasources", json={
            "name": "lakehouse-bench", "kind": "trino", "dsn": LAKE_DSN})
        created.raise_for_status()
        lake = created.json()

    name = "bench-ingest-%d" % int(time.time())
    started = time.time()
    job = http.post("/api/v1/engine/jobs", json={
        "engine": "spark", "name": name, "spec": SPEC})
    job.raise_for_status()
    job_id = job.json()["id"]
    print("submitted %s (job %d, %d rows, %d executors)"
          % (name, job_id, ROWS, EXECUTORS))

    current = {}
    while time.time() - started < WAIT_S:
        current = http.get("/api/v1/engine/jobs/%d" % job_id).json()
        if current["status"] in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(15)
    else:
        print("ingest did not finish within %ds" % WAIT_S)
        return 2
    if current["status"] != "succeeded":
        print("ingest %s: %s" % (current["status"], current.get("error")))
        return 2

    ingest_s = time.time() - started
    print("ingest   %7.1fs  %8.0f rows/s" % (ingest_s, ROWS / ingest_s))

    parts = TARGET.split(".")
    files_ref = '"%s$files"' % parts[2] if len(parts) == 3 else TARGET
    for label, template in QUERIES:
        if template is None:
            sql = ("SELECT sum(file_size_in_bytes) AS bytes, "
                   "count(*) AS files FROM %s.%s.%s"
                   % (parts[0], parts[1], files_ref))
        else:
            sql = template % TARGET
        t0 = time.time()
        response = http.post("/api/v1/workbench/query", json={
            "datasource_id": lake["id"], "sql": sql, "limit": 100})
        elapsed = time.time() - t0
        if response.status_code != 200:
            print("%-9s FAILED %s" % (label, response.text[:160]))
            continue
        result = response.json()
        note = ""
        if label == "size" and result["rows"]:
            size = result["rows"][0]
            note = "  %.2f GB in %d files" % (
                (size.get("bytes") or 0) / 1e9, size.get("files") or 0)
        print("%-9s %7.2fs  %6d rows%s"
              % (label, elapsed, result.get("row_count", 0), note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
