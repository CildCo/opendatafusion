import httpx

PROJECTS = ["retail", "wholesale", "logistics", "finance", "marketing",
            "support", "data_lab", "sandbox", "ops", "archive"]
USERS = [("viewer", "ViewerPassw0rd!"), ("editor", "EditorPassw0rd!"),
         ("approver", "ApproverPassw0rd!"), ("admin", "AdminPassw0rd!"),
         ("auditor", "AuditorPassw0rd!")]


class Client:
    def __init__(self, base_url: str, username: str, password: str,
                 transport=None):
        self.http = httpx.Client(base_url=base_url + "/api/v1",
                                 transport=transport, timeout=60)
        self.username = username
        self.password = password
        self.token = ""

    def login(self, project_id: int = 1) -> None:
        r = self.http.post("/auth/login", json={
            "username": self.username, "password": self.password,
            "project_id": project_id})
        r.raise_for_status()
        self.token = r.json()["token"]

    def _headers(self) -> dict:
        return {"Authorization": "Bearer " + self.token} if self.token else {}

    def get(self, path: str, **kw):
        r = self.http.get(path, headers=self._headers(), **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, **kw):
        r = self.http.post(path, headers=self._headers(), **kw)
        r.raise_for_status()
        return r.json()

    def publish(self, action: str, target: int, project_id: int = 1) -> None:
        cid = self.post("/changes", json={
            "project_id": project_id, "action": action, "target": target,
            "payload": {}})["id"]
        token = self.post(f"/changes/{cid}/approve", json={})["approval_token"]
        self.post(f"/changes/{cid}/apply", params={"approval_token": token},
                  json={})


def seed(base_url: str, datasource_ids: dict[str, int]) -> dict:
    admin = Client(base_url, "acceptance", "AcceptPassw0rd!")
    admin.login()
    projects = {"default": 1}
    for i, code in enumerate(PROJECTS[:9], start=2):
        p = admin.post("/projects", json={"code": code, "name": code})
        projects[code] = p["id"]
    created = {}
    for code, pid in projects.items():
        for role, password in USERS:
            username = f"{code}-{role}"
            user = admin.post("/users", json={
                "username": username, "password": password, "role": role})
            admin.post(f"/projects/{pid}/members",
                       json={"user_id": user["id"], "role": role})
        created[code] = {"project_id": pid, "assets": {}}
    return {"admin_token": admin.token, "projects": created,
            "datasources": datasource_ids}


def seed_datasources(admin: Client,
                     dsns: dict[str, tuple[str, str, str]]) -> dict:
    out = {}
    for key, (name, dsn, kind) in dsns.items():
        out[key] = admin.post("/datasources", json={
            "name": name, "dsn": dsn, "kind": kind})["id"]
    return out


def seed_assets(admin: Client, ds: dict[str, int],
                projects: dict[str, int]) -> dict:
    from bench.seed import assets as content
    catalog = admin.get("/catalog/datasets")
    catalog_id = next(
        x["id"] for x in catalog
        if x["datasource_id"] == ds["shop"] and x["table"] == "orders")
    counts = {"pipelines": 0, "datasets": 0, "metrics": 0, "dashboards": 0,
              "apps": 0, "apis": 0, "quality_rules": 0}
    for code, pid in projects.items():
        for suffix in ("orders", "items"):
            body = content.pipeline_content(
                ds["shop"], ds["mart"], "orders",
                f"orders_clean_{code}_{suffix}")
            aid = admin.post("/pipelines", json={
                "project_id": pid, "name": f"{code}-{suffix}",
                "content": body})["id"]
            admin.publish("publish_pipeline", aid, pid)
            counts["pipelines"] += 1
        datasets = []
        for i in range(5):
            body = content.dataset_content(
                ds["shop"], "orders",
                ["id", "customer_id", "amount", "discount", "status",
                 "created_at"])
            did = admin.post("/datasets", json={
                "project_id": pid, "name": f"{code}-ds-{i}",
                "content": body})["id"]
            admin.publish("publish_dataset", did, pid)
            datasets.append(did)
            counts["datasets"] += 1
        metrics = []
        for i, column in enumerate(("amount", "*", "discount")):
            body = content.metric_content(datasets[i], column)
            mid = admin.post("/metrics", json={
                "project_id": pid, "name": f"{code}-m-{i}",
                "content": body})["id"]
            admin.publish("publish_metric", mid, pid)
            metrics.append(mid)
            counts["metrics"] += 1
        for i in range(2):
            body = content.dashboard_content([metrics[i]], [datasets[i]])
            did = admin.post("/dashboards", json={
                "project_id": pid, "name": f"{code}-dash-{i}",
                "content": body})["id"]
            admin.publish("publish_dashboard", did, pid)
            counts["dashboards"] += 1
        body = content.app_content(datasets[0], metrics[0])
        aid = admin.post("/apps", json={
            "project_id": pid, "name": f"{code}-app",
            "content": body})["id"]
        admin.publish("publish_app", aid, pid)
        counts["apps"] += 1
        for i in range(2):
            body = content.api_content(ds["shop"], "orders")
            aid = admin.post("/apis", json={
                "project_id": pid, "name": f"{code}-api-{i}",
                "content": body})["id"]
            admin.publish("publish_api", aid, pid)
            counts["apis"] += 1
        for i in range(10):
            body = content.quality_rule(catalog_id, "amount")
            admin.post("/quality/rules", json={"project_id": pid, **body})
            counts["quality_rules"] += 1
    return counts
