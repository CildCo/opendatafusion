import time

import pyarrow as pa

from odf.assets.service import get_asset
from odf.models import AssetVersion, Datasource, PipelineNodeRun
from odf.pipeline.nodes import sink as _sink  # noqa: F401  register nodes
from odf.pipeline.nodes import source as _source  # noqa: F401
from odf.pipeline.nodes import transform as _transform  # noqa: F401
from odf.pipeline.nodes.base import RunContext, get_node
from odf.pipeline.schema import (input_edges, topo_order, upstream_nodes,
                                 validate_dag)

PREVIEW_BATCH = 1000
PREVIEW_TIMEOUT_S = 30


class PipelineRunError(Exception):
    def __init__(self, node_id, message, stats=None):
        super().__init__(message)
        self.node_id = node_id
        self.message = message
        self.stats = stats or {}


def _check_datasources(session, content, project_id):
    for node in content.get("nodes") or []:
        if node.get("type") not in ("source", "sink"):
            continue
        ds_id = (node.get("config") or {}).get("datasource_id")
        ds = session.get(Datasource, ds_id) if ds_id else None
        if not ds or ds.project_id != project_id:
            raise ValueError(
                "datasource %s does not belong to this project" % ds_id)


def execute_pipeline(session, asset_id, job_id=None, actor="system",
                     preview=False, target_node=None, limit=None,
                     content_override=None, cursor_override=None,
                     persist_cursor=True, until_cursor=None,
                     batch_override=None):
    asset = get_asset(session, asset_id)
    if not asset:
        raise ValueError("asset not found")
    if content_override is not None:
        content = content_override
    else:
        vid = asset.draft_version_id if preview else asset.published_version_id
        version = session.get(AssetVersion, vid) if vid else None
        if not version:
            raise ValueError("content not found")
        content = version.content_json
    errs = validate_dag(content, for_preview=preview)
    if errs:
        raise ValueError("invalid dag: %s" % errs)
    _check_datasources(session, content, asset.project_id)

    nodes = {n["id"]: n for n in content["nodes"]}
    if target_node and target_node not in nodes:
        raise ValueError("node not found: %s" % target_node)

    settings = content.get("settings") or {}
    batch = max(1, int(batch_override or settings.get("batch", 1000)))
    if preview:
        batch = min(batch, PREVIEW_BATCH)
    cursors = {} if preview else dict(asset.cursor_json or {})
    if cursor_override and not preview:
        cursors.update(cursor_override)
    ctx = RunContext(session=session, cursors=cursors, batch=batch,
                     preview=preview,
                     timeout_s=PREVIEW_TIMEOUT_S if preview else None,
                     cursor_override=cursor_override or {},
                     until_cursor=until_cursor,
                     persist_cursor=persist_cursor)
    order = topo_order(content)
    if target_node:
        allowed = {target_node} | upstream_nodes(content, target_node)
        order = [n for n in order if n in allowed]

    deadline = time.time() + PREVIEW_TIMEOUT_S if preview else None
    tables = {}
    stats = {}
    sink_failed = False
    for nid in order:
        if deadline and time.time() > deadline:
            raise PipelineRunError(nid, "preview timeout", stats)
        node = nodes[nid]
        inputs = [tables[e["from"]] for e in input_edges(content, nid)
                  if e["from"] in tables]
        started = time.time()
        ctx.current_node = nid
        try:
            table = get_node(node["type"])().run(
                inputs, node.get("config") or {}, ctx)
            ms = int((time.time() - started) * 1000)
            tables[nid] = table
            stats[nid] = {"rows": table.num_rows, "ms": ms,
                          "status": "success"}
            if not preview and job_id:
                session.add(PipelineNodeRun(
                    job_id=job_id, asset_id=asset_id, node_id=nid,
                    status="success",
                    in_num=sum(t.num_rows for t in inputs),
                    out_num=table.num_rows, ms=ms))
        except Exception as e:
            ms = int((time.time() - started) * 1000)
            stats[nid] = {"rows": 0, "ms": ms, "status": "failed",
                          "error": str(e)}
            if not preview and job_id:
                session.add(PipelineNodeRun(
                    job_id=job_id, asset_id=asset_id, node_id=nid,
                    status="failed", ms=ms, error=str(e)))
            on_error = (node.get("on_error")
                        or (node.get("config") or {}).get("on_error")
                        or "fail")
            if on_error in ("skip", "quarantine") and not preview:
                if node["type"] == "sink":
                    sink_failed = True
                fallback = inputs[0] if inputs else pa.table({})
                tables[nid] = fallback
                stats[nid]["policy"] = on_error
                continue
            session.commit()
            raise PipelineRunError(nid, str(e), stats) from e
    if not preview and persist_cursor and not sink_failed:
        merged = dict(asset.cursor_json or {})
        for nid, value in ctx.new_cursors.items():
            if value is not None:
                merged[nid] = value
        asset.cursor_json = merged
    session.commit()
    out = tables.get(target_node) if target_node else tables.get(order[-1])
    rows = out.slice(0, limit or 100).to_pylist() if out is not None else []
    source_ids = [nid for nid, n in nodes.items()
                  if n.get("type") == "source"]
    return {"rows": rows, "node_stats": stats,
            "new_cursors": dict(ctx.new_cursors),
            "exhausted": bool(source_ids) and all(
                nid in ctx.exhausted_nodes for nid in source_ids),
            "source_rows": sum(stats.get(nid, {}).get("rows", 0)
                               for nid in source_ids),
            "sink_failed": sink_failed,
            "cursor": next(iter(ctx.new_cursors.values()), None)}


def backfill_content_error(content) -> str | None:
    sources = [n for n in (content or {}).get("nodes") or []
               if n.get("type") == "source"]
    if not sources:
        return "pipeline has no source"
    if any(not (n.get("config") or {}).get("cursor_column")
           for n in sources):
        return "backfill requires a cursor column on every source"
    return None


def _save_job_result(session, job_id, result):
    if not job_id:
        return
    from odf.models import Job
    job = session.get(Job, job_id)
    if job:
        payload = dict(job.payload_json or {})
        payload["last_result"] = result
        job.payload_json = payload
        session.commit()


def _save_job_cursors(session, job_id, cursors):
    if not job_id:
        return
    from odf.models import Job
    job = session.get(Job, job_id)
    if job:
        payload = dict(job.payload_json or {})
        payload["resume_cursors"] = dict(cursors)
        job.payload_json = payload
        session.commit()


def execute_backfill(session, asset_id, start_cursor, end_cursor=None,
                     batch=None, max_batches=100, actor="system",
                     job_id=None, content_override=None,
                     resume_cursors=None):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "pipeline":
        raise ValueError("pipeline not found")
    if not start_cursor:
        raise ValueError("start_cursor is required")
    if not content_override:
        version = (session.get(AssetVersion, asset.published_version_id)
                   if asset.published_version_id else None)
        if not version:
            raise ValueError("pipeline is not published")
        content = version.content_json
    else:
        content = content_override
    err = backfill_content_error(content)
    if err:
        raise ValueError(err)
    sources = [n for n in content.get("nodes") or []
               if n.get("type") == "source"]
    cursors = {n["id"]: start_cursor for n in sources}
    if resume_cursors:
        cursors.update({k: v for k, v in resume_cursors.items()
                        if k in cursors and v is not None})
    sink_ids = [n["id"] for n in content.get("nodes") or []
                if n.get("type") == "sink"]
    rows_in = rows_out = batches = 0
    exhausted = False
    try:
        limit = max(1, int(max_batches))
    except (TypeError, ValueError):
        raise ValueError("max_batches must be a number")
    for _ in range(limit):
        out = execute_pipeline(
            session, asset_id, job_id=job_id, actor=actor,
            content_override=content, cursor_override=cursors,
            persist_cursor=False, until_cursor=end_cursor,
            batch_override=batch)
        if out.get("sink_failed"):
            raise ValueError("backfill stopped because a sink failed")
        batches += 1
        rows_in += out["source_rows"]
        rows_out += sum(out["node_stats"].get(nid, {}).get("rows", 0)
                        for nid in sink_ids
                        if out["node_stats"].get(nid, {}).get("status")
                        == "success")
        progressed = any(str(out["new_cursors"].get(nid)) != str(
            cursors.get(nid)) for nid in cursors)
        for nid, value in out["new_cursors"].items():
            if value is not None:
                cursors[nid] = value
        _save_job_cursors(session, job_id, cursors)
        if out["source_rows"] == 0 or out["exhausted"] or not progressed:
            exhausted = out["exhausted"]
            break
    result = {"batches": batches, "rows_in": rows_in, "rows_out": rows_out,
              "cursors": cursors, "exhausted": exhausted}
    _save_job_result(session, job_id, result)
    return result
