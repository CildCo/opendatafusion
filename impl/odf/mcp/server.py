import functools
import inspect
import re
from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

TOOLS = {}
WRITE_TOOLS = set()
APPROVER_TOOLS = {"publish_pipeline", "rollback_pipeline", "publish_api",
                  "revoke_api", "rollback_flow", "publish_interface",
                  "revoke_interface", "submit_app_form"}
CURRENT_PROJECT = ContextVar("mcp_project", default=None)
_HIDDEN_ARGS = {"approval_token"}

_WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|merge|copy|create|alter|drop|truncate|"
    r"grant|revoke|call|do|set|reset)\b", re.I)


def _project():
    return CURRENT_PROJECT.get()


def _ops_project(project_id=None):
    ctx = _project()
    if ctx is not None:
        if project_id is not None and project_id != ctx:
            raise PermissionError("project mismatch")
        return ctx
    if project_id is None:
        raise PermissionError("project context required")
    return project_id


def _check_datasource(session, datasource_id):
    from odf.models import Datasource
    ds = session.get(Datasource, datasource_id)
    if not ds:
        raise ValueError("datasource not found")
    project = _project()
    if project is not None and ds.project_id != project:
        raise PermissionError("datasource not found")
    return ds


def _check_asset(session, asset_id, expected_type=None):
    from odf.models import Asset
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    project = _project()
    if project is not None and a.project_id != project:
        raise PermissionError("asset not found")
    if expected_type and a.type != expected_type:
        raise ValueError("%s asset required" % expected_type)
    return a


def _audit(name, kwargs, ok, error=None):
    try:
        from odf.db import SessionLocal
        from odf.services.audit import write_audit
        safe = {}
        for k, v in kwargs.items():
            if k in _HIDDEN_ARGS:
                continue
            if isinstance(v, (int, float, bool)) or v is None:
                safe[k] = v
            else:
                safe[k] = str(v)[:300]
        target = str(kwargs.get("asset_id") or kwargs.get("run_id")
                     or kwargs.get("flow_id") or kwargs.get("interface_id")
                     or kwargs.get("change_id") or kwargs.get("project_id")
                     or "platform")
        detail = {"args": safe, "ok": ok}
        if error:
            detail["error"] = str(error)[:500]
        with SessionLocal() as s:
            write_audit(s, "mcp", name, target, detail)
    except Exception:
        pass


def tool(name, write=False, audit=True):
    def deco(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                call_args = dict(bound.arguments)
            except TypeError:
                call_args = dict(kwargs)
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                if audit:
                    _audit(name, call_args, False, e)
                raise
            if audit:
                _audit(name, call_args, True)
            return result
        if write:
            WRITE_TOOLS.add(name)
        TOOLS[name] = wrapped
        return wrapped
    return deco


def tool_catalog():
    out = []
    for name, fn in sorted(TOOLS.items()):
        sig = inspect.signature(fn)
        params = []
        for p in sig.parameters.values():
            if p.name in _HIDDEN_ARGS:
                continue
            typ = getattr(p.annotation, "__name__", str(p.annotation))
            params.append({"name": p.name, "type": typ,
                           "required": p.default is inspect._empty,
                           "default": None if p.default is inspect._empty
                           else p.default})
        out.append({"name": name,
                    "description": (fn.__doc__ or "").strip(),
                    "write": name in WRITE_TOOLS,
                    "parameters": params})
    return out


def assert_read_only(sql: str) -> None:
    head = sql.strip().lower()
    if not (head.startswith("select") or head.startswith("with")):
        raise ValueError("query_sql only allows select/with")
    if _WRITE_WORDS.search(sql):
        raise ValueError("query_sql rejects data-modifying statements")
    if ";" in sql.rstrip().rstrip(";"):
        raise ValueError("query_sql allows a single statement")


@tool("platform_snapshot")
def platform_snapshot():
    """Counts and recent state for assets, jobs, alerts and datasources."""
    from odf.db import SessionLocal
    from odf.models import (Alert, Asset, Datasource, Flow, Interface, Job)
    with SessionLocal() as s:
        project = _project()
        asset_q = s.query(Asset)
        flow_q = s.query(Flow)
        ds_q = s.query(Datasource)
        if_q = s.query(Interface)
        if project is not None:
            asset_q = asset_q.filter_by(project_id=project)
            flow_q = flow_q.filter_by(project_id=project)
            ds_q = ds_q.filter_by(project_id=project)
            if_q = if_q.filter_by(project_id=project)
        assets = asset_q.all()
        counts = {}
        for a in assets:
            counts[a.type] = counts.get(a.type, 0) + 1
        job_q = s.query(Job)
        if project is not None:
            asset_ids = [a.id for a in assets]
            flow_ids = [f.id for f in flow_q.all()]
            job_q = job_q.filter(
                (Job.asset_id.in_(asset_ids)) | (Job.flow_id.in_(flow_ids)))
        jobs = job_q.order_by(Job.id.desc()).limit(10).all()
        alert_q = s.query(Alert).filter_by(status="open")
        if project is not None:
            alert_q = alert_q.filter_by(project_id=project)
        alerts = alert_q.order_by(Alert.id.desc()).limit(20).all()
        return {
            "asset_counts": counts,
            "assets": [{"id": a.id, "key": a.key, "name": a.name,
                        "type": a.type, "enabled": a.enabled}
                       for a in assets],
            "jobs": [{"id": j.id, "asset_id": j.asset_id,
                      "type": j.asset_type, "status": j.status,
                      "attempts": j.attempts, "last_error": j.last_error}
                     for j in jobs],
            "open_alerts": [{"id": a.id, "severity": a.severity,
                             "title": a.title} for a in alerts],
            "flows": [{"id": f.id, "name": f.name, "status": f.status}
                      for f in flow_q.all()],
            "datasources": [{"id": d.id, "name": d.name, "kind": d.kind}
                            for d in ds_q.all()],
            "interfaces": [{"id": i.id, "name": i.name, "status": i.status}
                           for i in if_q.all()],
        }


@tool("list_assets")
def list_assets(type: str = "", project_id: int = 0):
    """List assets, optionally filtered by type and project."""
    from odf.db import SessionLocal
    from odf.models import Asset
    project = _project()
    if project is not None:
        if project_id and project_id != project:
            raise PermissionError("project mismatch")
        project_id = project
    with SessionLocal() as s:
        q = s.query(Asset)
        if type:
            q = q.filter_by(type=type)
        if project_id:
            q = q.filter_by(project_id=project_id)
        return [{"id": a.id, "key": a.key, "name": a.name, "type": a.type,
                 "project_id": a.project_id, "enabled": a.enabled,
                 "published": a.published_version_id is not None}
                for a in q.order_by(Asset.id).all()]


@tool("get_asset")
def get_asset(asset_id: int):
    """Return an asset with draft/published content and version numbers."""
    from odf.db import SessionLocal
    from odf.models import AssetVersion
    with SessionLocal() as s:
        a = _check_asset(s, asset_id)
        draft = s.get(AssetVersion, a.draft_version_id) \
            if a.draft_version_id else None
        pub = s.get(AssetVersion, a.published_version_id) \
            if a.published_version_id else None
        return {"id": a.id, "key": a.key, "name": a.name, "type": a.type,
                "project_id": a.project_id, "enabled": a.enabled,
                "draft_version": draft.version if draft else None,
                "published_version": pub.version if pub else None,
                "draft": draft.content_json if draft else None,
                "published": pub.content_json if pub else None}


@tool("lineage")
def lineage(project_id: int = 0, asset_id: int = 0):
    """Return asset lineage edges and pipeline DAG edges."""
    from odf.db import SessionLocal
    from odf.models import AssetVersion, LineageEdge
    project = _project()
    if project is not None:
        if project_id and project_id != project:
            raise PermissionError("project mismatch")
        project_id = project
    with SessionLocal() as s:
        if asset_id:
            _check_asset(s, asset_id)
        q = s.query(LineageEdge)
        if project_id:
            q = q.filter_by(project_id=project_id)
        edges = [{"from_type": e.from_type, "from_id": e.from_id,
                  "to_type": e.to_type, "to_id": e.to_id}
                 for e in q.order_by(LineageEdge.id).all()]
        pipeline_edges = []
        if asset_id:
            a = _check_asset(s, asset_id)
            if a and a.type == "pipeline":
                vid = a.published_version_id or a.draft_version_id
                v = s.get(AssetVersion, vid) if vid else None
                if v:
                    pipeline_edges = [{"from": e["from"], "to": e["to"]}
                                      for e in (v.content_json.get("edges") or [])]
        return {"edges": edges, "pipeline_edges": pipeline_edges}


@tool("pipeline_schema")
def pipeline_schema(asset_id: int):
    """Return per-node input/output columns for a pipeline."""
    from odf.db import SessionLocal
    from odf.pipeline.schema_service import node_schemas
    with SessionLocal() as s:
        _check_asset(s, asset_id, "pipeline")
        return node_schemas(s, asset_id)


@tool("preview_node")
def preview_node(asset_id: int, node_id: str, limit: int = 100):
    """Preview a pipeline node and its ancestors without writing sinks."""
    from odf.db import SessionLocal
    from odf.pipeline.preview import preview_pipeline
    with SessionLocal() as s:
        _check_asset(s, asset_id, "pipeline")
        return preview_pipeline(s, asset_id, node_id, limit=limit)


@tool("test_api")
def test_api(asset_id: int, params: dict | None = None):
    """Execute the published version of an API asset."""
    from odf.db import SessionLocal
    from odf.apistudio.service import execute_published
    with SessionLocal() as s:
        _check_asset(s, asset_id, "api")
        return execute_published(s, asset_id, params or {}, role="viewer")


@tool("dataset_schema")
def dataset_schema(asset_id: int):
    """Return columns/types for a dataset asset."""
    from odf.db import SessionLocal
    from odf.modelstudio.service import dataset_schema as _schema
    with SessionLocal() as s:
        _check_asset(s, asset_id, "dataset")
        return _schema(s, asset_id)


@tool("query_metric")
def query_metric(asset_id: int, limit: int = 100):
    """Run a published metric and return aggregated rows."""
    from odf.db import SessionLocal
    from odf.modelstudio.service import query_metric as _query
    with SessionLocal() as s:
        _check_asset(s, asset_id, "metric")
        return _query(s, asset_id, limit=limit, published_only=True,
                      role="viewer")


@tool("dashboard_data")
def dashboard_data(asset_id: int, params: dict | None = None,
                   limit: int = 100):
    """Execute the published version of a dashboard and return widget data."""
    from odf.db import SessionLocal
    from odf.dashboards.service import dashboard_data as _data
    with SessionLocal() as s:
        _check_asset(s, asset_id, "dashboard")
        return _data(s, asset_id, params=params, limit=limit,
                     published_only=True, role="viewer")


@tool("app_data")
def app_data(asset_id: int, page_id: str = "", params: dict | None = None,
             limit: int = 100):
    """Execute a published app page and return component data."""
    from odf.db import SessionLocal
    from odf.appstudio.service import app_data as _data
    with SessionLocal() as s:
        _check_asset(s, asset_id, "app")
        return _data(s, asset_id, page_id=page_id or None,
                     params=params or {}, limit=limit, published_only=True,
                     role="viewer")


@tool("submit_app_form", write=True, audit=False)
def submit_app_form(asset_id: int, component_id: str, values: dict,
                    approval_token: str, change_id: int,
                    project_id: int | None = None):
    """Submit an app form after a human approves this change."""
    from datetime import datetime, timezone
    from odf.db import SessionLocal
    from odf.appstudio.forms import submit_form
    from odf.models import ChangeRequest
    from odf.services.approval import verify_token
    project = _ops_project(project_id)
    with SessionLocal() as s:
        asset = _check_asset(s, asset_id, "app")
        if asset.project_id != project:
            raise PermissionError("asset not found")
        change = s.get(ChangeRequest, change_id)
        if not change or change.action != "app_form_submit" or                 int(change.target) != asset_id or                 change.project_id != project or change.status != "proposed":
            raise PermissionError("approval required")
        if not verify_token(asset_id, "app_form_submit", approval_token,
                            nonce=str(change_id)):
            raise PermissionError("approval required")
        change.status = "applied"
        change.applied_at = datetime.now(timezone.utc)
        s.commit()
        return submit_form(s, asset_id, component_id, values,
                           published_only=True, actor="mcp",
                           actor_role="approver")


@tool("ops_summary")
def ops_summary(project_id: int | None = None):
    """Return project job, alert and flow-health counts."""
    from odf.db import SessionLocal
    from odf.ops.service import summary
    with SessionLocal() as s:
        return summary(s, _ops_project(project_id))


@tool("list_jobs")
def list_jobs(status: str = "", limit: int = 50,
              project_id: int | None = None):
    """List project jobs, optionally filtered by status."""
    from odf.db import SessionLocal
    from odf.ops.service import list_jobs as _list
    with SessionLocal() as s:
        return _list(s, _ops_project(project_id), status or None, limit)


@tool("list_alerts")
def list_alerts(status: str = "", project_id: int | None = None):
    """List project alerts, optionally filtered by status."""
    from odf.db import SessionLocal
    from odf.ops.service import list_alerts as _list
    with SessionLocal() as s:
        return _list(s, _ops_project(project_id), status or None)


@tool("retry_job", write=True, audit=False)
def retry_job(job_id: int, project_id: int | None = None):
    """Requeue a failed project job."""
    from odf.db import SessionLocal
    from odf.ops.service import retry_job as _retry
    with SessionLocal() as s:
        return _retry(s, _ops_project(project_id), job_id, "mcp")


@tool("ack_alert", write=True, audit=False)
def ack_alert(alert_id: int, project_id: int | None = None):
    """Acknowledge a project alert."""
    from odf.db import SessionLocal
    from odf.ops.service import ack_alert as _ack
    with SessionLocal() as s:
        return _ack(s, _ops_project(project_id), alert_id, "mcp")


@tool("list_runs")
def list_runs(asset_id: int = 0, limit: int = 50):
    """List recent pipeline jobs, optionally for one asset."""
    from odf.db import SessionLocal
    from odf.models import Asset, Flow, Job
    with SessionLocal() as s:
        q = s.query(Job)
        project = _project()
        if asset_id:
            _check_asset(s, asset_id)
            q = q.filter_by(asset_id=asset_id)
        elif project is not None:
            asset_ids = [a.id for a in s.query(Asset)
                         .filter_by(project_id=project).all()]
            flow_ids = [f.id for f in s.query(Flow)
                        .filter_by(project_id=project).all()]
            q = q.filter((Job.asset_id.in_(asset_ids))
                         | (Job.flow_id.in_(flow_ids)))
        rows = q.order_by(Job.id.desc()).limit(max(1, min(limit, 200))).all()
        return [{"id": j.id, "asset_id": j.asset_id,
                 "asset_type": j.asset_type, "status": j.status,
                 "attempts": j.attempts, "last_error": j.last_error,
                 "created_at": j.created_at.isoformat()}
                for j in rows]


@tool("diagnose_run")
def diagnose_run(run_id: int):
    """Diagnose a failed job or connector flow run with node evidence."""
    from odf.db import SessionLocal
    from odf.models import Flow, FlowRun, Job, PipelineNodeRun
    with SessionLocal() as s:
        project = _project()
        job = s.get(Job, run_id)
        if job:
            if job.asset_id:
                _check_asset(s, job.asset_id)
            elif job.flow_id:
                flow = s.get(Flow, job.flow_id)
                if not flow or (project is not None
                                and flow.project_id != project):
                    raise PermissionError("run not found")
            elif project is not None:
                raise PermissionError("run not found")
            nodes = (s.query(PipelineNodeRun)
                     .filter_by(job_id=job.id)
                     .order_by(PipelineNodeRun.id).all())
            hints, evidence = [], []
            for n in nodes:
                if n.status == "failed":
                    hints.append("节点 %s 失败：%s" % (n.node_id, n.error))
                    evidence.append({"node_id": n.node_id,
                                     "in_num": n.in_num,
                                     "out_num": n.out_num,
                                     "error": n.error})
            if job.last_error:
                hints.append("job 错误：%s" % job.last_error)
            if job.status == "queued":
                hints.append("job 已排队：检查 worker 是否在线")
            if job.status == "running":
                hints.append("job 运行中：检查 worker 心跳与锁")
            if job.attempts >= job.max_attempts:
                hints.append("已达到最大重试次数")
            return {"kind": "job",
                    "job": {"id": job.id, "asset_id": job.asset_id,
                            "status": job.status, "attempts": job.attempts,
                            "last_error": job.last_error},
                    "nodes": [{"node_id": n.node_id, "status": n.status,
                               "in_num": n.in_num, "out_num": n.out_num,
                               "ms": n.ms, "error": n.error}
                              for n in nodes],
                    "hints": hints, "evidence": evidence}
        run = s.get(FlowRun, run_id)
        if not run:
            raise ValueError("run not found")
        flow = s.get(Flow, run.flow_id)
        if not flow or (project is not None and flow.project_id != project):
            raise PermissionError("run not found")
        h = flow_health.__wrapped__(run.flow_id)
        return {"kind": "flow_run",
                "flow_run": {"id": run.id, "flow_id": run.flow_id,
                             "status": run.status, "err_num": run.err_num,
                             "cursor_value": run.cursor_value},
                "health": h,
                "hints": ["flow run 状态 %s，错误行 %s" %
                          (run.status, run.err_num)],
                "evidence": [h]}


@tool("create_pipeline_draft", write=True)
def create_pipeline_draft(name: str, content: dict, project_id: int = 1):
    """Create a pipeline asset with a draft version."""
    from odf.assets.service import create_asset
    from odf.db import SessionLocal
    project = _project() or project_id
    with SessionLocal() as s:
        a = create_asset(s, project, "pipeline", name, content,
                         "mcp", enabled=False)
        return {"id": a.id, "key": a.key}


@tool("update_pipeline_draft", write=True)
def update_pipeline_draft(asset_id: int, content: dict):
    """Replace a pipeline draft with new content."""
    from odf.assets.service import update_draft
    from odf.db import SessionLocal
    with SessionLocal() as s:
        _check_asset(s, asset_id, "pipeline")
        v = update_draft(s, asset_id, content, "mcp")
        return {"asset_id": asset_id, "version": v.version}


@tool("validate_pipeline")
def validate_pipeline(content: dict, project_id: int = 0):
    """Validate a pipeline DAG and its source/sink schema without writing."""
    from odf.db import SessionLocal
    from odf.pipeline.validate import validate_pipeline_content
    with SessionLocal() as s:
        errs = validate_pipeline_content(
            s, content, project_id or _project() or 0)
    return {"valid": not errs, "errors": errs}


@tool("create_api_draft", write=True)
def create_api_draft(name: str, content: dict, project_id: int = 1):
    """Create an API asset with a draft version."""
    from odf.apistudio.content import empty_content
    from odf.assets.service import create_asset
    from odf.db import SessionLocal
    project = _project() or project_id
    with SessionLocal() as s:
        a = create_asset(s, project, "api", name,
                         content or empty_content(), "mcp", enabled=False)
        return {"id": a.id, "key": a.key}


@tool("update_api_draft", write=True)
def update_api_draft(asset_id: int, content: dict):
    """Replace an API draft with new content."""
    from odf.assets.service import update_draft
    from odf.db import SessionLocal
    with SessionLocal() as s:
        _check_asset(s, asset_id, "api")
        v = update_draft(s, asset_id, content, "mcp")
        return {"asset_id": asset_id, "version": v.version}


def _require_token(target, action, token):
    from odf.services.approval import verify_token
    if not verify_token(target, action, token):
        raise PermissionError("approval required")


@tool("publish_pipeline", write=True)
def publish_pipeline(asset_id: int, approval_token: str):
    """Publish a pipeline draft; requires an approval token."""
    _require_token(asset_id, "publish_pipeline", approval_token)
    from odf.assets.service import publish_asset
    from odf.db import SessionLocal
    with SessionLocal() as s:
        _check_asset(s, asset_id, "pipeline")
        v = publish_asset(s, asset_id, "mcp")
        return {"asset_id": asset_id, "version": v.version}


@tool("rollback_pipeline", write=True)
def rollback_pipeline(asset_id: int, version: int, approval_token: str):
    """Rollback a pipeline to a published version."""
    _require_token(asset_id, "rollback_pipeline", approval_token)
    from odf.assets.service import rollback_asset
    from odf.db import SessionLocal
    with SessionLocal() as s:
        _check_asset(s, asset_id, "pipeline")
        v = rollback_asset(s, asset_id, version, "mcp")
        return {"asset_id": asset_id, "version": v.version}


@tool("run_pipeline", write=True)
def run_pipeline(asset_id: int, approval_token: str):
    """Enqueue one run for a published pipeline."""
    _require_token(asset_id, "run_pipeline", approval_token)
    from odf.db import SessionLocal
    from odf.services.jobs import enqueue_asset
    with SessionLocal() as s:
        a = _check_asset(s, asset_id, "pipeline")
        if not a.published_version_id:
            raise ValueError("pipeline is not published")
        job = enqueue_asset(s, a.id, "pipeline")
        return {"asset_id": asset_id, "job_id": job.id}


@tool("pause_pipeline", write=True)
def pause_pipeline(asset_id: int, approval_token: str):
    """Disable pipeline scheduling."""
    _require_token(asset_id, "pause_pipeline", approval_token)
    from odf.db import SessionLocal
    with SessionLocal() as s:
        a = _check_asset(s, asset_id, "pipeline")
        a.enabled = False
        s.commit()
        return {"asset_id": asset_id, "enabled": False}


@tool("resume_pipeline", write=True)
def resume_pipeline(asset_id: int, approval_token: str):
    """Enable pipeline scheduling."""
    _require_token(asset_id, "resume_pipeline", approval_token)
    from odf.db import SessionLocal
    with SessionLocal() as s:
        a = _check_asset(s, asset_id, "pipeline")
        a.enabled = True
        s.commit()
        return {"asset_id": asset_id, "enabled": True}


@tool("publish_api", write=True)
def publish_api(asset_id: int, approval_token: str):
    """Publish an API draft; requires an approval token."""
    _require_token(asset_id, "publish_api", approval_token)
    from odf.assets.service import publish_asset
    from odf.db import SessionLocal
    with SessionLocal() as s:
        _check_asset(s, asset_id, "api")
        v = publish_asset(s, asset_id, "mcp")
        return {"asset_id": asset_id, "version": v.version}


@tool("revoke_api", write=True)
def revoke_api(asset_id: int, approval_token: str):
    """Disable a published API."""
    _require_token(asset_id, "revoke_api", approval_token)
    from odf.db import SessionLocal
    with SessionLocal() as s:
        a = _check_asset(s, asset_id, "api")
        a.enabled = False
        s.commit()
        return {"asset_id": asset_id, "enabled": False}


@tool("list_flows")
def list_flows(project_id: int = 0):
    from odf.db import SessionLocal
    from odf.models import Flow
    pid = _ops_project(project_id or None)
    with SessionLocal() as s:
        q = s.query(Flow).filter_by(project_id=pid)
        return [{"id": f.id, "name": f.name, "cron": f.cron,
                 "status": f.status} for f in q.all()]


@tool("list_datasources")
def list_datasources(project_id: int = 0):
    from odf.db import SessionLocal
    from odf.models import Datasource
    from odf.services.datasource import get_dsn, mask_dsn
    pid = _ops_project(project_id or None)
    with SessionLocal() as s:
        q = s.query(Datasource).filter_by(project_id=pid)
        return [{"id": d.id, "name": d.name, "kind": d.kind,
                 "dsn": mask_dsn(get_dsn(d))} for d in q.all()]


@tool("flow_health")
def flow_health(flow_id: int, period_s: int = 0):
    from odf.db import SessionLocal
    from odf.models import Flow, FlowRun
    from odf.services.health import compute_health, cron_period_seconds
    with SessionLocal() as s:
        flow = s.get(Flow, flow_id)
        runs = (s.query(FlowRun).filter_by(flow_id=flow_id)
                .order_by(FlowRun.id.desc()).limit(20).all())
        period = period_s or cron_period_seconds(flow.cron)
        return {"flow_id": flow_id, "name": flow.name,
                **compute_health(runs, datetime.now(timezone.utc), period)}


@tool("diagnose_flow")
def diagnose_flow(flow_id: int):
    h = flow_health.__wrapped__(flow_id)
    hints = []
    if h.get("empty_rounds", 0) >= 3:
        hints.append("连续空转：检查源库游标与过滤条件")
    if h.get("status") == "critical":
        hints.append("滞后超阈值：检查调度、worker、源库连通性")
    return {"health": h, "hints": hints}


@tool("pause_flow", write=True)
def pause_flow(flow_id: int, approval_token: str):
    from odf.services.approval import verify_token
    if not verify_token(flow_id, "pause", approval_token):
        raise PermissionError("approval required")
    from odf.db import SessionLocal
    from odf.models import Flow
    with SessionLocal() as s:
        f = s.get(Flow, flow_id)
        f.status = 0
        s.commit()
        return {"flow_id": flow_id, "status": f.status}


@tool("resume_flow", write=True)
def resume_flow(flow_id: int, approval_token: str):
    from odf.services.approval import verify_token
    if not verify_token(flow_id, "resume", approval_token):
        raise PermissionError("approval required")
    from odf.db import SessionLocal
    from odf.models import Flow
    with SessionLocal() as s:
        f = s.get(Flow, flow_id)
        f.status = 1
        s.commit()
        return {"flow_id": flow_id, "status": f.status}


@tool("get_flow")
def get_flow(flow_id: int):
    from odf.db import SessionLocal
    from odf.models import Flow, FlowVersion
    with SessionLocal() as s:
        f = s.get(Flow, flow_id)
        if not f:
            return None
        v = (s.query(FlowVersion)
             .filter_by(flow_id=f.id, version=f.current_version).first())
        return {"id": f.id, "name": f.name, "cron": f.cron,
                "status": f.status, "version": f.current_version,
                "dag": v.dag_json if v else None}


@tool("get_interface")
def get_interface(interface_id: int):
    from odf.db import SessionLocal
    from odf.models import Interface
    with SessionLocal() as s:
        i = s.get(Interface, interface_id)
        if not i:
            return None
        return {"id": i.id, "key": i.interface_key, "name": i.name,
                "sql": i.sql_text, "status": i.status}


@tool("search_catalog")
def search_catalog_tool(q: str, limit: int = 50, project_id: int | None = None):
    """Search table and column names in the current project."""
    from odf.db import SessionLocal
    from odf.services.catalog import search_catalog
    with SessionLocal() as s:
        return search_catalog(s, _ops_project(project_id), q, limit)


@tool("get_pipeline_cursors")
def get_pipeline_cursors(asset_id: int):
    """Show incremental source cursors for a pipeline."""
    from odf.db import SessionLocal
    from odf.pipeline.cursors import list_cursors
    with SessionLocal() as s:
        a = _check_asset(s, asset_id, "pipeline")
        return list_cursors(s, a)


@tool("reset_pipeline_cursor", write=True)
def reset_pipeline_cursor(asset_id: int, node_id: str, cursor: str = ""):
    """Set or clear one pipeline source cursor (empty clears it)."""
    from odf.db import SessionLocal
    from odf.pipeline.cursors import set_cursor
    with SessionLocal() as s:
        a = _check_asset(s, asset_id, "pipeline")
        out = set_cursor(s, a, node_id, cursor or None)
        return out


@tool("test_datasource")
def test_datasource(datasource_id: int):
    from odf.db import SessionLocal
    from odf.models import Datasource
    from odf.services.datasource import get_dsn, test_connection
    with SessionLocal() as s:
        try:
            ds = _check_datasource(s, datasource_id)
        except (ValueError, PermissionError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": test_connection(get_dsn(ds), kind=ds.kind)}


@tool("list_changes")
def list_changes(status: str = ""):
    from odf.db import SessionLocal
    from odf.services.changes import list_changes as _list
    with SessionLocal() as s:
        return [{"id": c.id, "action": c.action, "target": c.target,
                 "status": c.status} for c in _list(s, status or None)]


@tool("propose_change", write=True)
def propose_change(project_id: int, actor: str, action: str, target: int,
                   payload: dict | None = None):
    from odf.db import SessionLocal
    from odf.services.changes import propose
    with SessionLocal() as s:
        c = propose(s, project_id, actor, action, target, payload)
        return {"id": c.id, "status": c.status}


@tool("apply_change", write=True, audit=False)
def apply_change(change_id: int, approval_token: str):
    from odf.db import SessionLocal
    from odf.services.changes import apply
    with SessionLocal() as s:
        c = apply(s, change_id, approval_token)
        return {"id": c.id, "status": c.status}


@tool("rollback_flow", write=True)
def rollback_flow(flow_id: int, version: int, approval_token: str):
    from odf.services.approval import verify_token
    if not verify_token(flow_id, "rollback", approval_token):
        raise PermissionError("approval required")
    from odf.db import SessionLocal
    from odf.models import Flow
    with SessionLocal() as s:
        f = s.get(Flow, flow_id)
        if not f:
            raise ValueError("flow not found")
        f.current_version = version
        s.commit()
        return {"flow_id": flow_id, "version": version}


@tool("publish_interface", write=True)
def publish_interface(interface_id: int, approval_token: str):
    from odf.services.approval import verify_token
    if not verify_token(interface_id, "publish", approval_token):
        raise PermissionError("approval required")
    from odf.db import SessionLocal
    from odf.models import Interface
    with SessionLocal() as s:
        i = s.get(Interface, interface_id)
        if not i:
            raise ValueError("interface not found")
        i.status = 1
        s.commit()
        return {"interface_id": interface_id, "status": 1}


@tool("revoke_interface", write=True)
def revoke_interface(interface_id: int, approval_token: str):
    from odf.services.approval import verify_token
    if not verify_token(interface_id, "revoke", approval_token):
        raise PermissionError("approval required")
    from odf.db import SessionLocal
    from odf.models import Interface
    with SessionLocal() as s:
        i = s.get(Interface, interface_id)
        if not i:
            raise ValueError("interface not found")
        i.status = 0
        s.commit()
        return {"interface_id": interface_id, "status": 0}
@tool("query_sql")
def query_sql(datasource_id: int, sql: str):
    assert_read_only(sql)
    from odf.db import SessionLocal
    from odf.models import Datasource
    from odf.services.datasource import (connect_args_for, get_dsn,
                                         prepare_connection)
    from odf.services.sqldialect import limited
    with SessionLocal() as s:
        ds = _check_datasource(s, datasource_id)
        from odf.services.masking import datasource_has_policies
        if datasource_has_policies(s, ds.id):
            raise PermissionError(
                "query_sql is disabled for governed datasources")
        if ds.kind in ("file", "clickhouse"):
            from odf import clickhouse, filesource
            wrapped = limited(sql, "sqlite", 10000)
            if ds.kind == "file":
                return filesource.execute(ds, wrapped, {}, 10000)["rows"]
            return clickhouse.execute(ds, wrapped, {}, 10000)["rows"]
        dsn = get_dsn(ds)
        e = create_engine(dsn, connect_args=connect_args_for(ds.kind, dsn))
        with e.begin() as c:
            if e.dialect.name == "postgresql":
                c.execute(text("set transaction read only"))
            prepare_connection(c, e.dialect.name, 60000)
            rows = c.execute(
                text(limited(sql, ds.kind, 10000))).mappings().all()
        return [dict(r) for r in rows]