import secrets
import time

import pyarrow as pa

from odf.pipeline.nodes.base import NodeExecutor, register_node
from odf.settings import get_settings

WAIT_POLL_S = 2
_SPARK_KEYS = ("image", "main_application_file", "args", "spark_version",
               "service_account", "driver_cores", "driver_memory",
               "executor_cores", "executor_instances", "executor_memory",
               "spark_conf", "namespace")


def job_name(config, asset_id):
    name = (config.get("name") or "").strip().lower()
    if not name:
        name = "odf-%s-%s" % (asset_id or 0, secrets.token_hex(4))
    return name[:63].strip("-")


def _spark_spec(config):
    return {key: config[key] for key in _SPARK_KEYS if key in config}


def _flink_spec(config):
    return {"statement": config.get("statement") or "",
            "properties": config.get("properties") or {},
            "attached": bool(config.get("attached", False))}


def _record_lineage(ctx, config):
    target = config.get("target_table")
    if not target or not ctx.project_id:
        return
    from odf.pipeline.lineage import _ensure
    for ref in config.get("source_tables") or []:
        _ensure(ctx.session, ctx.project_id, "table", str(ref), str(ref),
                "table", target, target, asset_id=ctx.asset_id)
    ctx.session.commit()


def run_engine_node(engine, config, ctx):
    if ctx.preview:
        raise ValueError("engine nodes cannot run in preview")
    from odf.services.engine_jobs import submit_job, sync_job

    spec = _spark_spec(config) if engine == "spark" else _flink_spec(config)
    job = submit_job(ctx.session, ctx.project_id, engine,
                     job_name(config, ctx.asset_id), spec, ctx.actor,
                     asset_id=ctx.asset_id)
    if config.get("wait", True):
        settings = get_settings()
        timeout = float(config.get("timeout_s")
                        or settings.engine_job_timeout_s)
        deadline = time.time() + timeout
        while job.status in ("pending", "running"):
            if time.time() > deadline:
                raise RuntimeError("engine job timed out: %s" % job.name)
            time.sleep(WAIT_POLL_S)
            job = sync_job(ctx.session, job)
    if job.status == "failed":
        raise RuntimeError(job.error or "engine job failed")
    if job.status == "cancelled":
        raise RuntimeError("engine job cancelled")
    if job.status in ("pending", "running"):
        ctx.dispatched.add(ctx.current_node)
    _record_lineage(ctx, config)
    return pa.table({})


@register_node("spark")
class SparkNode(NodeExecutor):
    def schema(self, inputs, config):
        return []

    def run(self, inputs, config, ctx):
        return run_engine_node("spark", config, ctx)


@register_node("flink_sql")
class FlinkSqlNode(NodeExecutor):
    def schema(self, inputs, config):
        return []

    def run(self, inputs, config, ctx):
        return run_engine_node("flink", config, ctx)
