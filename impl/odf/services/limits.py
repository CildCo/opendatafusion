from datetime import datetime, timedelta, timezone

from odf.models import (Asset, AssetVersion, Datasource, Job,
                        LakehouseMaintenance, QueryRun)


class RateLimited(ValueError):
    pass


def limits_of(datasource):
    raw = datasource.limit_json or {}
    out = {}
    for key in ("max_queries_per_min", "max_running_jobs"):
        try:
            value = int(raw.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        out[key] = max(0, value)
    return out


def usage(session, datasource_id):
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    queries = (session.query(QueryRun)
               .filter(QueryRun.datasource_id == datasource_id,
                       QueryRun.created_at >= since).count())
    running = running_for_datasource(session, datasource_id)
    return {"queries_last_min": queries, "running_jobs": running}


def check_query_rate(session, datasource):
    limit = limits_of(datasource)["max_queries_per_min"]
    if not limit:
        return
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    used = (session.query(QueryRun)
            .filter(QueryRun.datasource_id == datasource.id,
                    QueryRun.created_at >= since).count())
    if used >= limit:
        raise RateLimited(
            "datasource query rate limit reached (%d/min)" % limit)


def _version_content(session, asset):
    version_id = asset.published_version_id or asset.draft_version_id
    version = session.get(AssetVersion, version_id) if version_id else None
    return (version.content_json or {}) if version else {}


def job_datasource(session, job):
    if job.asset_type == "model" and job.asset_id:
        asset = session.get(Asset, job.asset_id)
        if asset:
            value = _version_content(session, asset).get("datasource_id")
            return value if isinstance(value, int) else None
        return None
    if job.asset_type == "lakehouse_maintenance":
        schedule_id = (job.payload_json or {}).get("schedule_id")
        row = session.get(LakehouseMaintenance, schedule_id) \
            if isinstance(schedule_id, int) else None
        return row.datasource_id if row else None
    return None


def running_for_datasource(session, datasource_id, exclude_job_id=None):
    jobs = (session.query(Job)
            .filter(Job.status == "running",
                    Job.asset_type.in_(("model", "lakehouse_maintenance")))
            .all())
    total = 0
    for job in jobs:
        if exclude_job_id is not None and job.id == exclude_job_id:
            continue
        if job_datasource(session, job) == datasource_id:
            total += 1
    return total


def job_slot_ok(session, datasource_id, exclude_job_id=None):
    datasource = session.get(Datasource, datasource_id)
    if not datasource:
        return True
    limit = limits_of(datasource)["max_running_jobs"]
    if not limit:
        return True
    return running_for_datasource(session, datasource_id,
                                  exclude_job_id) < limit
