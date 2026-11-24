from sqlalchemy import func

from odf.models import Asset, Job, ProjectMember, Project


def _limit(project, key):
    quota = project.quota_json or {}
    try:
        value = int(quota.get(key) or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def usage(session, project_id):
    assets = (session.query(Asset.type, func.count(Asset.id))
              .filter(Asset.project_id == project_id)
              .group_by(Asset.type).all())
    asset_ids = [row[0] for row in session.query(Asset.id)
                 .filter(Asset.project_id == project_id).all()]
    if not asset_ids:
        return {"assets": 0, "assets_by_type": {},
                "jobs": {"queued": 0, "running": 0, "failed": 0},
                "members": 0, "quota": {}}
    job_q = session.query(Job.status, func.count(Job.id)).filter(
        Job.asset_id.in_(asset_ids))
    jobs = {status: count for status, count in job_q.group_by(Job.status).all()}
    return {"assets": sum(count for _, count in assets),
            "assets_by_type": {kind: count for kind, count in assets},
            "jobs": {"queued": jobs.get("queued", 0),
                     "running": jobs.get("running", 0),
                     "failed": jobs.get("failed", 0)},
            "members": (session.query(func.count(ProjectMember.id))
                        .filter_by(project_id=project_id).scalar() or 0),
            "quota": (session.get(Project, project_id).quota_json or {})
            if session.get(Project, project_id) else {}}


def check_asset(session, project_id):
    project = session.get(Project, project_id)
    limit = _limit(project, "max_assets") if project else None
    if limit is None:
        return
    count = session.query(func.count(Asset.id)).filter(
        Asset.project_id == project_id).scalar() or 0
    if count >= limit:
        raise ValueError("project asset quota reached (%d)" % limit)


def check_job(session, project_id):
    project = session.get(Project, project_id)
    limit = _limit(project, "max_jobs") if project else None
    if limit is None:
        return
    asset_ids = [row[0] for row in session.query(Asset.id)
                 .filter(Asset.project_id == project_id).all()]
    if not asset_ids:
        return
    q = session.query(func.count(Job.id)).filter(
        Job.status.in_(("queued", "running")),
        Job.asset_id.in_(asset_ids))
    if (q.scalar() or 0) >= limit:
        raise ValueError("project job quota reached (%d)" % limit)
