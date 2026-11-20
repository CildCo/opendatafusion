from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from odf.models import Asset, Flow, FlowRun, Job, JobDependency

TYPES = ("flow", "pipeline")
DEFAULT_WINDOW_HOURS = 24


def _object(session, project_id, kind, object_id):
    if kind == "flow":
        row = session.get(Flow, object_id)
        return row if row and row.project_id == project_id else None
    if kind == "pipeline":
        row = session.get(Asset, object_id)
        if not row or row.project_id != project_id or row.type != "pipeline":
            return None
        return row
    return None


def _name(session, project_id, kind, object_id):
    row = _object(session, project_id, kind, object_id)
    return row.name if row else "#%s" % object_id


def _reaches(session, project_id, start_type, start_id, target_type,
             target_id):
    seen = set()
    queue = [(start_type, start_id)]
    while queue:
        kind, object_id = queue.pop()
        if (kind, object_id) in seen:
            continue
        seen.add((kind, object_id))
        rows = (session.query(JobDependency)
                .filter_by(project_id=project_id, upstream_type=kind,
                           upstream_id=object_id).all())
        for row in rows:
            if (row.downstream_type, row.downstream_id) == (target_type,
                                                           target_id):
                return True
            queue.append((row.downstream_type, row.downstream_id))
    return False


def add_dependency(session, project_id, downstream_type, downstream_id,
                   upstream_type, upstream_id):
    for kind in (downstream_type, upstream_type):
        if kind not in TYPES:
            raise ValueError("unsupported object type")
    if (downstream_type, downstream_id) == (upstream_type, upstream_id):
        raise ValueError("an object cannot depend on itself")
    if not _object(session, project_id, downstream_type, downstream_id):
        raise ValueError("downstream object not found")
    if not _object(session, project_id, upstream_type, upstream_id):
        raise ValueError("upstream object not found")
    if _reaches(session, project_id, downstream_type, downstream_id,
                upstream_type, upstream_id):
        raise ValueError("dependency would create a cycle")
    existing = (session.query(JobDependency)
                .filter_by(project_id=project_id,
                           downstream_type=downstream_type,
                           downstream_id=downstream_id,
                           upstream_type=upstream_type,
                           upstream_id=upstream_id).first())
    if existing:
        return existing
    row = JobDependency(project_id=project_id,
                        downstream_type=downstream_type,
                        downstream_id=downstream_id,
                        upstream_type=upstream_type,
                        upstream_id=upstream_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_dependencies(session, project_id):
    rows = (session.query(JobDependency).filter_by(project_id=project_id)
            .order_by(JobDependency.id).all())
    return [{"id": row.id,
             "downstream_type": row.downstream_type,
             "downstream_id": row.downstream_id,
             "downstream_name": _name(session, project_id,
                                      row.downstream_type,
                                      row.downstream_id),
             "upstream_type": row.upstream_type,
             "upstream_id": row.upstream_id,
             "upstream_name": _name(session, project_id, row.upstream_type,
                                    row.upstream_id)}
            for row in rows]


def delete_dependency(session, project_id, dependency_id):
    row = (session.query(JobDependency)
           .filter_by(id=dependency_id, project_id=project_id).first())
    if not row:
        raise ValueError("dependency not found")
    session.delete(row)
    session.commit()


def _last_success(session, project_id, kind, object_id):
    if kind == "flow":
        row = (session.query(FlowRun)
               .filter(FlowRun.flow_id == object_id,
                       FlowRun.status == 2)
               .order_by(FlowRun.finished_at.desc().nulls_last(),
                         FlowRun.id.desc()).first())
        return row.finished_at or row.started_at if row else None
    row = (session.query(Job)
           .filter(Job.asset_type == "pipeline", Job.asset_id == object_id,
                   Job.status == "success")
           .order_by(Job.finished_at.desc().nulls_last(),
                     Job.id.desc()).first())
    return row.finished_at or row.created_at if row else None


def dependencies_satisfied(session, project_id, downstream_type,
                          downstream_id, now=None, window_hours=None):
    now = now or datetime.now(timezone.utc)
    window = int(window_hours or DEFAULT_WINDOW_HOURS)
    cutoff = now - timedelta(hours=window)
    deps = (session.query(JobDependency)
            .filter_by(project_id=project_id,
                       downstream_type=downstream_type,
                       downstream_id=downstream_id).all())
    blocked = []
    for dep in deps:
        last = _last_success(session, project_id, dep.upstream_type,
                             dep.upstream_id)
        if not last:
            blocked.append({"type": dep.upstream_type,
                            "id": dep.upstream_id,
                            "name": _name(session, project_id,
                                          dep.upstream_type,
                                          dep.upstream_id),
                            "reason": "no successful run"})
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last < cutoff:
            blocked.append({"type": dep.upstream_type,
                            "id": dep.upstream_id,
                            "name": _name(session, project_id,
                                          dep.upstream_type,
                                          dep.upstream_id),
                            "reason": "last success is older than %dh"
                                      % window})
    return {"satisfied": not blocked, "blocked": blocked,
            "window_hours": window}
