from datetime import datetime, timezone

from dataclasses import replace

from odf.engine import FlinkSqlGateway, JobSpec, JobStatus, KubernetesEngine
from odf.engine.profiles import (spark_conf_profile,
                                 spark_default_image, spark_jar_volume)
from odf.models import Asset, EngineJob
from odf.services import tenancy
from odf.services.audit import write_audit
from odf.settings import get_settings

TERMINAL = (JobStatus.SUCCEEDED.value, JobStatus.FAILED.value,
            JobStatus.CANCELLED.value)
ACTIVE = (JobStatus.PENDING.value, JobStatus.RUNNING.value)
ENGINES = ("spark", "flink")


def _now():
    return datetime.now(timezone.utc)


def _spark_engine() -> KubernetesEngine:
    settings = get_settings()
    if not settings.k8s_api_url or not settings.k8s_token:
        raise ValueError("kubernetes engine is not configured")
    return KubernetesEngine.from_settings(settings)


def _flink_gateway() -> FlinkSqlGateway:
    settings = get_settings()
    if not settings.flink_sql_gateway_url:
        raise ValueError("Flink SQL Gateway is not configured")
    return FlinkSqlGateway(settings.flink_sql_gateway_url,
                           rest_url=settings.flink_rest_url)


def spark_spec_from(name: str, spec: dict, settings=None) -> JobSpec:
    settings = settings or get_settings()
    conf = spark_conf_profile(settings)
    conf.update(spec.get("spark_conf") or {})
    volumes, mounts, _ = spark_jar_volume(settings)
    return JobSpec(
        name=name,
        engine="spark",
        image=spec.get("image") or spark_default_image(settings),
        main_application_file=spec.get("main_application_file") or "",
        args=list(spec.get("args") or []),
        spark_version=spec.get("spark_version") or "3.5.1",
        service_account=spec.get("service_account") or "spark-operator-spark",
        driver_cores=int(spec.get("driver_cores") or 1),
        driver_memory=spec.get("driver_memory") or "1g",
        executor_cores=int(spec.get("executor_cores") or 1),
        executor_instances=int(spec.get("executor_instances") or 1),
        executor_memory=spec.get("executor_memory") or "1g",
        spark_conf=conf,
        namespace=spec.get("namespace") or None,
        volumes=volumes,
        volume_mounts=mounts,
    )


def _audit(session, job, action, detail=None):
    write_audit(session, job.submitted_by, action, str(job.id),
                dict(detail or {}, name=job.name, engine=job.engine))


def _count(status):
    from odf.api.metrics import inc
    inc("engine_jobs_total", status=status)


def _on_failure(session, job):
    from odf.services.alerts import raise_alert
    from odf.webhooks.service import emit_safe
    raise_alert(session, job.project_id, "error",
                "engine job failed: %s" % job.name,
                {"engine_job_id": job.id, "engine": job.engine,
                 "error": job.error or ""})
    emit_safe(session, job.project_id, "job.failed",
              {"engine_job_id": job.id, "name": job.name,
               "engine": job.engine})


def _dispatch(job):
    spec = job.spec_json or {}
    if job.engine == "spark":
        settings = get_settings()
        namespace = spec.get("namespace") or tenancy.namespace_for_project(
            job.project_id, settings)
        if namespace and not spec.get("namespace"):
            tenancy.ensure_project_namespace(job.project_id,
                                             settings=settings)
        job_spec = spark_spec_from(job.name, spec, settings)
        if namespace:
            job_spec = replace(job_spec, namespace=namespace)
        return _spark_engine().submit(job_spec), {}, None
    statement = (spec.get("statement") or "").strip()
    if not statement:
        raise ValueError("flink job requires a statement")
    attached = bool(spec.get("attached", True))
    result = _flink_gateway().execute(
        statement, spec.get("properties") or {}, attached=attached)
    if attached:
        return "", result, JobStatus.SUCCEEDED.value
    return result["job_id"], {}, None


def submit_job(session, project_id, engine, name, spec, actor,
               asset_id=None):
    if engine not in ENGINES:
        raise ValueError("unsupported engine: %s" % engine)
    if asset_id is not None:
        asset = session.get(Asset, asset_id)
        if not asset or asset.project_id != project_id:
            raise ValueError("asset does not belong to this project")
    if session.query(EngineJob).filter_by(name=name).first():
        raise ValueError("engine job name already exists")

    job = EngineJob(project_id=project_id, asset_id=asset_id, engine=engine,
                    name=name, spec_json=dict(spec or {}), status="pending",
                    submitted_by=actor, attempts=0, max_attempts=2)
    session.add(job)
    session.commit()
    session.refresh(job)

    last_error = None
    for attempt in range(1, job.max_attempts + 1):
        job.attempts = attempt
        try:
            external_id, result, terminal = _dispatch(job)
        except Exception as error:
            last_error = error
            session.commit()
            continue
        job.external_id = external_id
        job.result_json = result or {}
        job.started_at = _now()
        job.synced_at = _now()
        if terminal:
            job.status = terminal
            job.finished_at = _now()
        else:
            job.status = JobStatus.RUNNING.value
        session.commit()
        _audit(session, job, "engine_job_submitted",
               {"attempts": job.attempts})
        _count(job.status)
        return job

    job.status = JobStatus.FAILED.value
    job.error = str(last_error)[:1000]
    job.finished_at = _now()
    session.commit()
    _audit(session, job, "engine_job_failed",
           {"attempts": job.attempts, "error": job.error})
    _count(job.status)
    _on_failure(session, job)
    raise ValueError("engine submission failed: %s" % str(last_error)[:300])


def sync_job(session, job):
    if job.status in TERMINAL or not job.external_id:
        return job
    error = ""
    if job.engine == "spark":
        engine = _spark_engine()
        status = engine.status(job.name)
        if status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            try:
                error = engine.result(job.name).get("error") or ""
            except Exception:
                error = ""
    else:
        status = _flink_gateway().job_status(job.external_id)
    job.synced_at = _now()
    if status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
        job.status = status.value
        job.finished_at = _now()
        if status == JobStatus.FAILED:
            job.error = error[:1000] or "engine job failed"
    elif status == JobStatus.RUNNING:
        job.status = JobStatus.RUNNING.value
    session.commit()
    if job.status in TERMINAL:
        _audit(session, job, "engine_job_finished",
               {"status": job.status, "error": job.error or ""})
        _count(job.status)
        if job.status == JobStatus.FAILED.value:
            _on_failure(session, job)
    return job


def cancel_job(session, job, actor):
    if job.status in TERMINAL:
        return job
    if job.external_id:
        if job.engine == "spark":
            _spark_engine().cancel(job.name)
        else:
            _flink_gateway().cancel(job.external_id)
    job.status = JobStatus.CANCELLED.value
    job.finished_at = _now()
    job.synced_at = _now()
    session.commit()
    write_audit(session, actor, "engine_job_cancelled", str(job.id),
                {"name": job.name, "engine": job.engine})
    _count(job.status)
    return job


def savepoint_job(session, job, target_dir, stop, actor):
    if job.engine != "flink":
        raise ValueError("savepoints are only available for flink jobs")
    if not job.external_id:
        raise ValueError("flink job has no running job id")
    result = _flink_gateway().savepoint(job.external_id, target_dir or "",
                                        bool(stop))
    write_audit(session, actor, "engine_job_savepoint", str(job.id),
                {"trigger": result.get("trigger_id"),
                 "location": result.get("location"), "stop": bool(stop)})
    if stop:
        job.status = JobStatus.CANCELLED.value
        job.finished_at = _now()
        job.synced_at = _now()
        session.commit()
    return result


def get_job(session, project_id, job_id):
    job = session.get(EngineJob, job_id)
    if not job or job.project_id != project_id:
        return None
    return job


def list_jobs(session, project_id, status=None, engine=None, limit=100):
    query = session.query(EngineJob).filter_by(project_id=project_id)
    if status:
        query = query.filter(EngineJob.status == status)
    if engine:
        query = query.filter(EngineJob.engine == engine)
    return (query.order_by(EngineJob.id.desc())
            .limit(max(1, min(int(limit), 500))).all())


def sync_due(session, limit=20):
    rows = (session.query(EngineJob)
            .filter(EngineJob.status.in_(ACTIVE),
                    EngineJob.external_id != "")
            .order_by(EngineJob.id).limit(limit).all())
    count = 0
    for job in rows:
        try:
            sync_job(session, job)
            count += 1
        except Exception:
            session.rollback()
    return count


def job_out(job):
    return {
        "id": job.id,
        "project_id": job.project_id,
        "asset_id": job.asset_id,
        "engine": job.engine,
        "name": job.name,
        "status": job.status,
        "external_id": job.external_id,
        "submitted_by": job.submitted_by,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "error": job.error,
        "result": job.result_json or {},
        "spec": job.spec_json or {},
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "synced_at": job.synced_at,
    }
