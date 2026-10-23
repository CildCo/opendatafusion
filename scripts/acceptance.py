import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

PREFIX = "/api/v1"


class CheckFailure(Exception):
    pass


def expect(condition, message):
    if not condition:
        raise CheckFailure(message)


def sign256(sk: str, text: str) -> str:
    return base64.b64encode(
        hmac.new(sk.encode(), text.encode(), hashlib.sha256).digest()
    ).decode()


class Echo(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.received.append(self.rfile.read(length))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


class Acceptance:
    def __init__(self, base, username, password, workdir, mcp_base):
        self.base = base.rstrip("/")
        self.mcp_base = mcp_base.rstrip("/")
        self.username = username
        self.password = password
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.run_id = (time.strftime("%Y%m%d%H%M%S")
                       + "-" + uuid.uuid4().hex[:8])
        self.client = httpx.Client(base_url=self.base, timeout=60)
        self.mcp = httpx.Client(base_url=self.mcp_base, timeout=60)
        self.token = ""
        self.results = []
        self.ids = {}

    def call(self, method, path, expected=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.token:
            headers.setdefault("Authorization", "Bearer " + self.token)
        r = self.client.request(method, PREFIX + path, headers=headers,
                                **kwargs)
        if expected is not None:
            expect(r.status_code == expected,
                   "%s %s expected %s got %s: %s"
                   % (method, path, expected, r.status_code, r.text[:500]))
        return r

    def step(self, name):
        started = time.time()

        def deco(fn):
            try:
                detail = fn()
                self.results.append({"name": name, "ok": True,
                                     "ms": int((time.time() - started) * 1000),
                                     "detail": detail})
            except Exception as e:
                self.results.append({
                    "name": name, "ok": False,
                    "ms": int((time.time() - started) * 1000),
                    "error": str(e)[:800],
                    "trace": traceback.format_exc()[-1200:]})
            return fn
        return deco

    def login(self, username, password):
        r = self.client.post(PREFIX + "/auth/login", json={
            "username": username, "password": password, "project_id": 1})
        expect(r.status_code == 200, "login failed: %s" % r.text)
        return r.json()["token"]

    def change(self, action, target, payload=None):
        r = self.call("POST", "/changes", 200, json={
            "project_id": 1, "action": action, "target": target,
            "payload": payload or {}})
        cid = r.json()["id"]
        token = self.call("POST", f"/changes/{cid}/approve", 200,
                          json={}).json()["approval_token"]
        self.call("POST", f"/changes/{cid}/apply", 200, json={},
                  params={"approval_token": token})
        return cid

    def poll_job(self, asset_id, job_id, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            rows = self.call("GET", f"/pipelines/{asset_id}/jobs",
                             200).json()
            job = next((j for j in rows if j["id"] == job_id), None)
            if job and job["status"] in ("success", "failed"):
                return job
            time.sleep(1)
        raise CheckFailure("job %s did not finish" % job_id)

    def run(self):
        steps = [
            ("health", self.health),
            ("auth-rbac-revocation", self.auth),
            ("datasource-metadata-workbench", self.datasources),
            ("pipeline-run", self.pipeline),
            ("pipeline-backfill-cursor", self.backfill),
            ("dataset-metric-policy", self.modelstudio),
            ("api-gateway-sha256", self.gateway),
            ("catalog-search-lineage-impact", self.catalog),
            ("quality-rules", self.quality),
            ("files", self.files),
            ("webhook-delivery", self.webhooks),
            ("mcp-auth-tools", self.mcp_check),
            ("metrics", self.metrics),
        ]
        for name, fn in steps:
            self.step(name)(fn)
        return self.results

    def health(self):
        for path in ("/livez", "/readyz", "/healthz"):
            r = self.client.get(path)
            expect(r.status_code == 200, "%s failed" % path)
        ui = self.client.get("/ui/")
        expect(ui.status_code == 200 and "assets/index-" in ui.text,
               "UI assets missing")
        spec = self.client.get("/openapi.json").json()
        for path in ("/api/v1/pipelines/{asset_id}/backfill",
                     "/api/v1/catalog/search",
                     "/api/v1/datasets/{asset_id}/column-policies"):
            expect(path in spec["paths"], "missing route %s" % path)
        return {"livez": "ok", "readyz": "ok", "routes": 3}

    def auth(self):
        bad = self.client.post(PREFIX + "/auth/login", json={
            "username": self.username, "password": "wrong-pass"})
        expect(bad.status_code == 401, "wrong password was accepted")
        self.token = self.login(self.username, self.password)
        me = self.call("GET", "/auth/me", 200).json()
        expect(me["role"] == "admin", "admin role missing")
        user = f"accept-viewer-{self.run_id}"
        password = f"Viewer-{secrets.token_hex(6)}-A1!"
        uid = self.call("POST", "/users", 200, json={
            "username": user, "password": password,
            "role": "viewer"}).json()["id"]
        self.call("POST", "/projects/1/members", 200, json={
            "user_id": uid, "role": "viewer"})
        viewer = self.login(user, password)
        r = self.client.get(PREFIX + "/users", headers={
            "Authorization": "Bearer " + viewer})
        expect(r.status_code == 403, "viewer accessed admin users")
        r = self.client.post(PREFIX + "/auth/change-password", headers={
            "Authorization": "Bearer " + viewer}, json={
                "old_password": password,
                "new_password": f"Viewer-{secrets.token_hex(6)}-B2!"})
        expect(r.status_code == 200 and r.json().get("token"),
               "password change did not return a token")
        old = self.client.get(PREFIX + "/auth/me", headers={
            "Authorization": "Bearer " + viewer})
        expect(old.status_code == 401, "old session survived password change")
        return {"viewer_id": uid, "revocation": "ok"}

    def datasources(self):
        self.ids["src_db"] = self.workdir / ("source-%s.db" % self.run_id)
        self.ids["dst_db"] = self.workdir / ("target-%s.db" % self.run_id)
        for path, table in ((self.ids["src_db"], "accept_source"),
                            (self.ids["dst_db"], "accept_target")):
            con = sqlite3.connect(path)
            con.execute(f"create table {table} (id int primary key, v text)")
            if table == "accept_source":
                con.executemany(f"insert into {table} values (?,?)",
                                [(1, "alpha"), (2, "beta"), (3, "gamma")])
            con.commit()
            con.close()
            path.chmod(0o644)
        src = self.call("POST", "/datasources", 200, json={
            "name": f"accept-source-{self.run_id}",
            "dsn": "sqlite:///" + str(self.ids["src_db"]),
            "kind": "sqlite"}).json()["id"]
        dst = self.call("POST", "/datasources", 200, json={
            "name": f"accept-target-{self.run_id}",
            "dsn": "sqlite:///" + str(self.ids["dst_db"]),
            "kind": "sqlite"}).json()["id"]
        self.ids["src"], self.ids["dst"] = src, dst
        for did in (src, dst):
            expect(self.call("POST", f"/datasources/{did}/test", 200)
                   .json()["ok"] is True, "datasource test failed")
            expect(self.call("POST", f"/datasources/{did}/sync", 200)
                   .json()["tables"] >= 1, "metadata sync failed")
        tables = self.call("GET", f"/datasources/{src}/tables", 200).json()
        expect(any(t["table"] == "accept_source" for t in tables),
               "synced table missing")
        out = self.call("POST", "/workbench/query", 200, json={
            "datasource_id": src,
            "sql": "select count(*) as n from accept_source"}).json()
        expect(out["rows"][0]["n"] == 3, "workbench count mismatch")
        return {"source_id": src, "target_id": dst, "rows": 3}

    def pipeline(self):
        content = {
            "nodes": [
                {"id": "src", "type": "source",
                 "config": {"datasource_id": self.ids["src"],
                            "table": "accept_source", "pk": "id",
                            "cursor_column": "id"}},
                {"id": "dst", "type": "sink",
                 "config": {"datasource_id": self.ids["dst"],
                            "table": "accept_target", "pk": ["id"],
                            "mode": "upsert"}}],
            "edges": [{"from": "src", "to": "dst"}],
            "settings": {"batch": 10}}
        pid = self.call("POST", "/pipelines", 200, json={
            "project_id": 1, "name": f"accept-pipeline-{self.run_id}",
            "content": content}).json()["id"]
        self.ids["pipeline"] = pid
        self.change("publish_pipeline", pid)
        job = self.call("POST", f"/pipelines/{pid}/run", 200).json()["job_id"]
        result = self.poll_job(pid, job)
        expect(result["status"] == "success", "pipeline run failed: %s"
               % result.get("last_error"))
        out = self.call("POST", "/workbench/query", 200, json={
            "datasource_id": self.ids["dst"],
            "sql": "select count(*) as n from accept_target"}).json()
        expect(out["rows"][0]["n"] == 3, "sink rows mismatch")
        return {"pipeline_id": pid, "job_id": job}

    def backfill(self):
        con = sqlite3.connect(self.ids["dst_db"])
        con.execute("delete from accept_target")
        con.commit()
        con.close()
        r = self.call("POST", f"/pipelines/{self.ids['pipeline']}/backfill",
                      200, json={"start_cursor": "0", "max_batches": 10})
        job = self.poll_job(self.ids["pipeline"], r.json()["job_id"])
        expect(job["status"] == "success", "backfill job failed")
        out = self.call("POST", "/workbench/query", 200, json={
            "datasource_id": self.ids["dst"],
            "sql": "select count(*) as n from accept_target"}).json()
        expect(out["rows"][0]["n"] == 3, "backfill rows mismatch")
        cursors = self.call(
            "GET", f"/pipelines/{self.ids['pipeline']}/cursors", 200).json()
        src = next(s for s in cursors["sources"] if s["node_id"] == "src")
        expect(src["cursor_column"] == "id", "cursor metadata missing")
        self.call("PUT", f"/pipelines/{self.ids['pipeline']}/cursors", 200,
                  json={"node_id": "src", "cursor": "2"})
        got = self.call(
            "GET", f"/pipelines/{self.ids['pipeline']}/cursors", 200).json()
        expect(got["cursors"]["src"] == "2", "cursor reset failed")
        self.call("PUT", f"/pipelines/{self.ids['pipeline']}/cursors", 200,
                  json={"node_id": "src", "cursor": None})
        return {"backfill_rows": 3, "cursor": "ok"}

    def modelstudio(self):
        content = {"mode": "visual",
                   "query": {"datasource_id": self.ids["src"],
                             "table": "accept_source",
                             "select": [{"column": "id"},
                                        {"column": "v", "as": "label"}],
                             "limit": 100},
                   "params": [], "sql": None, "auth": None}
        did = self.call("POST", "/datasets", 200, json={
            "project_id": 1, "name": f"accept-dataset-{self.run_id}",
            "content": content}).json()["id"]
        self.ids["dataset"] = did
        self.change("publish_dataset", did)
        preview = self.call("POST", f"/datasets/{did}/preview", 200,
                            json={"limit": 10}).json()
        expect(preview["row_count"] == 3, "dataset preview count")
        policy = self.call("POST", f"/datasets/{did}/column-policies", 200,
                           json={"column": "v", "classification": "pii",
                                 "mask_type": "redact",
                                 "exempt_roles": []}).json()
        self.ids["column_policy"] = policy["id"]
        pols = self.call("GET", f"/datasets/{did}/column-policies", 200).json()
        expect(len(pols) == 1 and pols[0]["mask_type"] == "redact",
               "column policy missing")
        editor_name = f"accept-editor-{self.run_id}"
        editor_password = f"Editor-{secrets.token_hex(6)}-C3!"
        editor_id = self.call("POST", "/users", 200, json={
            "username": editor_name, "password": editor_password,
            "role": "editor"}).json()["id"]
        self.call("POST", "/projects/1/members", 200, json={
            "user_id": editor_id, "role": "editor"})
        editor_token = self.login(editor_name, editor_password)
        masked = self.client.post(
            PREFIX + f"/datasets/{did}/preview", json={"limit": 10},
            headers={"Authorization": "Bearer " + editor_token})
        expect(masked.status_code == 200, "editor preview failed")
        expect(all(r["label"] == "***" for r in masked.json()["rows"]),
               "column mask did not apply to editor preview")
        metric = {"dataset_id": did,
                  "measure": {"agg": "count", "column": "*", "as": "value"},
                  "dimensions": ["label"], "filters": [],
                  "format": {"type": "number"}}
        mid = self.call("POST", "/metrics", 200, json={
            "project_id": 1, "name": f"accept-metric-{self.run_id}",
            "content": metric}).json()["id"]
        self.change("publish_metric", mid)
        m = self.call("POST", f"/metrics/{mid}/query", 200,
                      json={"limit": 10}).json()
        expect(m["row_count"] == 3, "metric query count")
        masked_metric = self.client.post(
            PREFIX + f"/metrics/{mid}/query", json={"limit": 10},
            headers={"Authorization": "Bearer " + editor_token})
        expect(masked_metric.status_code == 200, "metric editor query failed")
        expect(all(r["label"] == "***" for r in masked_metric.json()["rows"]),
               "column mask did not apply to metric")
        self.ids["metric"] = mid
        return {"dataset_id": did, "metric_id": mid, "policy": "redact"}

    def gateway(self):
        content = {"mode": "visual",
                   "query": {"datasource_id": self.ids["src"],
                             "table": "accept_source",
                             "select": [{"column": "id"},
                                        {"column": "v"}],
                             "limit": 100},
                   "params": [], "sql": None,
                   "auth": {"type": "aksk", "rate_limit_per_min": 600}}
        aid = self.call("POST", "/apis", 200, json={
            "project_id": 1, "name": f"accept-api-{self.run_id}",
            "content": content}).json()["id"]
        self.ids["api"] = aid
        self.change("publish_api", aid)
        key = self.call("GET", f"/apis/{aid}", 200).json()["key"]
        cred = self.call("POST", "/projects/1/aksk", 200).json()
        project_code = self.call("GET", "/projects", 200).json()[0]["code"]
        body = b""
        date = str(int(time.time() * 1000))
        path = "/openapi/%s" % key
        s2s = "\n".join(["POST",
                         base64.b64encode(
                             hashlib.md5(body).digest()).decode(),
                         "application/json", date, path])
        signature = sign256(cred["sk"], s2s)
        r = self.client.post(path, content=body, headers={
            "projectKey": project_code,
            "Authorization": "%s:%s" % (cred["ak"], signature),
            "Content-Type": "application/json", "Date": date})
        expect(r.status_code == 200, "gateway call failed: %s" % r.text)
        expect(r.json()["total"] == 3, "gateway row count")
        stats = self.call("GET", "/api-stats", 200).json()
        expect(any(s["api_id"] == aid for s in stats), "api stats missing")
        self.ids["ak"] = cred["ak"]
        return {"api_id": aid, "key": key, "total": 3}

    def catalog(self):
        found = self.call("GET", "/catalog/search?q=accept_source", 200).json()
        expect(any(t["table"] == "accept_source" for t in found["tables"]),
               "catalog search failed")
        ref = f"{self.ids['src']}:accept_source"
        impact = self.call("GET", "/catalog/impact?ref="
                           + httpx.QueryParams({"ref": ref}).get("ref"),
                           200).json()
        expect(impact["edges"], "impact edges missing")
        lineage = self.call("GET", "/catalog/lineage", 200).json()
        expect(lineage["column_edges"], "column lineage missing")
        return {"search": 1, "impact_edges": len(impact["edges"]),
                "column_edges": len(lineage["column_edges"])}

    def quality(self):
        datasets = self.call("GET", "/catalog/datasets", 200).json()
        ds = next(d for d in datasets if d["datasource_id"] == self.ids["src"]
                  and d["table"] == "accept_source")
        rid = self.call("POST", "/quality/rules", 200, json={
            "project_id": 1, "dataset_id": ds["id"],
            "name": f"accept-not-null-{self.run_id}", "kind": "not_null",
            "column_name": "v", "config": {}}).json()["id"]
        out = self.call("POST", f"/quality/rules/{rid}/run", 200).json()
        expect(out["status"] == "pass", "quality rule failed")
        fresh = self.call("POST", "/quality/rules", 200, json={
            "project_id": 1, "dataset_id": ds["id"],
            "name": f"accept-schema-{self.run_id}", "kind": "schema",
            "column_name": None,
            "config": {"expected": ["id", "v"]}}).json()["id"]
        out = self.call("POST", f"/quality/rules/{fresh}/run", 200).json()
        expect(out["status"] == "pass", "schema rule failed")
        return {"metadata_dataset_id": ds["id"], "rules": 2}

    def files(self):
        payload = b"acceptance-file-" + self.run_id.encode()
        up = self.call("POST", "/files", 200,
                       files={"file": ("accept.txt", payload, "text/plain")})
        fid = up.json()["id"]
        down = self.call("GET", f"/files/{fid}/download", 200)
        expect(down.content == payload, "file content mismatch")
        self.call("DELETE", f"/files/{fid}", 200)
        return {"file_id": fid, "bytes": len(payload)}

    def mcp_check(self):
        expect(self.mcp.post("/mcp", json={}).status_code == 401,
               "MCP accepted unauthenticated request")
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/json, text/event-stream"}
        r = self.mcp.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26",
                       "capabilities": {},
                       "clientInfo": {"name": "acceptance",
                                      "version": "1"}}})
        expect(r.status_code == 200, "MCP initialize failed: %s" % r.text)
        headers["mcp-session-id"] = r.headers["mcp-session-id"]
        r = self.mcp.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {}})
        expect(r.status_code == 200 and "platform_snapshot" in r.text,
               "MCP tools/list failed")
        return {"auth": "ok", "tools": "ok"}

    def metrics(self):
        r = self.client.get("/metrics")
        expect(r.status_code == 200, "metrics endpoint failed")
        for needle in ("odf_requests_total",
                       "odf_request_duration_seconds_bucket",
                       "odf_queue_depth", "odf_db_pool_size",
                       "odf_uptime_seconds"):
            expect(needle in r.text, "metric missing: %s" % needle)
        return {"metrics": "ok"}

    def webhooks(self):
        server = ThreadingHTTPServer(("127.0.0.1", 18093), Echo)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            wid = self.call("POST", "/webhooks", 200, json={
                "name": f"accept-hook-{self.run_id}",
                "url": "http://127.0.0.1:18093/hook",
                "events": ["webhook.test"], "enabled": True}).json()["id"]
            self.call("POST", f"/webhooks/{wid}/test", 200, json={})
            deadline = time.time() + 20
            status = "pending"
            while time.time() < deadline:
                rows = self.call(
                    "GET", f"/webhooks/{wid}/deliveries", 200).json()
                if rows:
                    status = rows[0]["status"]
                    if status in ("success", "failed"):
                        break
                time.sleep(1)
            expect(status == "success", "webhook delivery status=%s" % status)
            expect(Echo.received, "webhook receiver got no request")
            self.call("DELETE", f"/webhooks/{wid}", 200)
            return {"delivery": "success"}
        finally:
            server.shutdown()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:18090")
    p.add_argument("--username", default="acceptance")
    p.add_argument("--password",
                   default=os.environ.get("ODF_ACCEPT_PASSWORD", ""))
    p.add_argument("--workdir", default="./acceptance-data")
    p.add_argument("--mcp-base", default="http://127.0.0.1:18092")
    p.add_argument("--report", default="")
    args = p.parse_args()
    if not args.password:
        p.error("--password or ODF_ACCEPT_PASSWORD is required")
    acc = Acceptance(args.base, args.username, args.password, args.workdir,
                     args.mcp_base)
    results = acc.run()
    failed = [r for r in results if not r["ok"]]
    report = {"base": args.base, "run_id": acc.run_id,
              "passed": len(results) - len(failed), "failed": len(failed),
              "results": results}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
