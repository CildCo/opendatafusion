"""Acceptance checks for the lakehouse integration.

Runs against a live control plane and cluster. Every check prints PASS or FAIL
and the process exits non-zero when any check fails.

    ODF_API=http://127.0.0.1:18080 \\
    ODF_USER=admin ODF_PASSWORD=... \\
    LAKE_DSN='trino://odf@<trino-host>:8080/iceberg/demo' \\
    python scripts/acceptance_lakehouse.py
"""

import os
import sys
import time

import httpx

API = os.environ.get("ODF_API", "http://127.0.0.1:18080").rstrip("/")
USER = os.environ.get("ODF_USER", "admin")
PASSWORD = os.environ.get("ODF_PASSWORD", "")
LAKE_DSN = os.environ.get(
    "LAKE_DSN", "trino://odf@127.0.0.1:8080/iceberg/demo")
SPARK_IMAGE = os.environ.get("SPARK_IMAGE", "apache/spark:3.5.1")
SPARK_MAIN = os.environ.get(
    "SPARK_MAIN", "local:///opt/spark/examples/src/main/python/pi.py")
WAIT_S = int(os.environ.get("WAIT_S", "300"))

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((name, True, detail or ""))
        print("PASS  %s  %s" % (name, detail or ""))
    except Exception as error:
        results.append((name, False, str(error)))
        print("FAIL  %s  %s" % (name, error))


class Client:
    def __init__(self):
        self.http = httpx.Client(base_url=API, timeout=60.0)
        self.token = ""

    def login(self):
        response = self.http.post("/api/v1/auth/login", json={
            "username": USER, "password": PASSWORD, "project_id": 1})
        response.raise_for_status()
        self.token = response.json()["token"]
        self.http.headers["Authorization"] = "Bearer " + self.token

    def get(self, path, **kw):
        response = self.http.get("/api/v1" + path, **kw)
        response.raise_for_status()
        return response.json()

    def post(self, path, body=None, **kw):
        response = self.http.post("/api/v1" + path, json=body or {}, **kw)
        response.raise_for_status()
        return response.json()

    def delete(self, path):
        response = self.http.delete("/api/v1" + path)
        response.raise_for_status()
        return response.json()


def main():
    client = Client()
    client.login()

    state = {}

    def create_datasource():
        body = {"name": "lakehouse-%d" % int(time.time()),
                "kind": "trino", "dsn": LAKE_DSN}
        created = client.post("/datasources", body)
        state["ds_id"] = created["id"]
        return "id=%d" % created["id"]

    def connection_ok():
        out = client.post("/datasources/%d/test" % state["ds_id"])
        assert out.get("ok") is True, out
        return "trino reachable"

    def schema_ready():
        out = client.post("/lakehouse/schema",
                          {"datasource_id": state["ds_id"]})
        state["schema"] = out["schema"]
        return out["schema"]

    def sync_catalog():
        out = client.post("/lakehouse/sync",
                          {"datasource_id": state["ds_id"]})
        state["tables"] = out["tables"]
        return "%d tables" % out["tables"]

    def list_tables():
        out = client.get("/lakehouse/tables?datasource_id=%d"
                         % state["ds_id"])
        state["table_names"] = [t["table"] for t in out["tables"]]
        return ", ".join(state["table_names"][:5]) or "no tables"

    def submit_spark():
        name = "acc-spark-%d" % int(time.time())
        job = client.post("/engine/jobs", {
            "engine": "spark", "name": name,
            "spec": {"image": SPARK_IMAGE,
                     "main_application_file": SPARK_MAIN,
                     "service_account": "spark-operator-spark",
                     "spark_conf": {"spark.kubernetes.namespace": "data"}},
        })
        state["spark_job"] = job["id"]
        return "job=%s" % job["name"]

    def spark_terminal():
        deadline = time.time() + WAIT_S
        while time.time() < deadline:
            job = client.get("/engine/jobs/%d" % state["spark_job"])
            if job["status"] in ("succeeded", "failed", "cancelled"):
                assert job["status"] == "succeeded", job.get("error")
                return job["status"]
            time.sleep(5)
        raise TimeoutError("spark job did not finish within %ds" % WAIT_S)

    def flink_sql():
        out = client.post("/engine/sql", {"statement": "SHOW CATALOGS"})
        assert out["result"].get("resultType") == "PAYLOAD", out
        return "sql gateway answered"

    def engine_jobs_listed():
        rows = client.get("/engine/jobs")
        ids = [r["id"] for r in rows]
        assert state["spark_job"] in ids, ids
        return "%d jobs" % len(rows)

    def audit_recorded():
        rows = client.get("/audit?limit=200")
        actions = {r.get("action") for r in rows}
        assert "engine_job_submitted" in actions, sorted(actions)[:10]
        assert "engine_sql" in actions, sorted(actions)[:10]
        return "engine actions audited"

    def cancel_path():
        name = "acc-cancel-%d" % int(time.time())
        job = client.post("/engine/jobs", {
            "engine": "flink", "name": name,
            "spec": {"statement": "SELECT 1", "attached": False}})
        client.delete("/engine/jobs/%d" % job["id"])
        after = client.get("/engine/jobs/%d" % job["id"])
        assert after["status"] in ("cancelled", "succeeded"), after["status"]
        return after["status"]

    check("create trino datasource", create_datasource)
    check("test datasource connection", connection_ok)
    check("create project schema", schema_ready)
    check("sync iceberg metadata", sync_catalog)
    check("list lakehouse tables", list_tables)
    check("submit spark job", submit_spark)
    check("spark job reaches terminal state", spark_terminal)
    check("run flink sql through the api", flink_sql)
    check("list engine jobs", engine_jobs_listed)
    check("audit engine actions", audit_recorded)
    check("cancel an engine job", cancel_path)

    failed = [name for name, ok, _ in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(failed)))
    if failed:
        print("failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
