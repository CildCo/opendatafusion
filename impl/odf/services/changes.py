from datetime import datetime, timezone

from odf.models import ChangeRequest, Flow, Interface
from odf.services.approval import verify_token
from odf.services.audit import write_audit


def propose(session, project_id: int, actor: str, action: str, target: int,
            payload: dict | None = None) -> ChangeRequest:
    c = ChangeRequest(project_id=project_id, actor=actor, action=action,
                      target=str(target), payload_json=payload or {},
                      status="proposed")
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def list_changes(session, status: str | None = None,
                 project_id: int | None = None):
    q = session.query(ChangeRequest)
    if status:
        q = q.filter_by(status=status)
    if project_id is not None:
        q = q.filter_by(project_id=project_id)
    return q.order_by(ChangeRequest.id.desc()).limit(200).all()


def _flow(session, flow_id, project_id):
    f = session.get(Flow, flow_id)
    if not f or f.project_id != project_id:
        raise ValueError("flow not found")
    return f


def _set_flow_status(session, flow_id: int, status: int,
                     project_id: int | None = None):
    f = session.get(Flow, flow_id)
    if not f or (project_id is not None and f.project_id != project_id):
        raise ValueError("flow not found")
    f.status = status
    session.commit()
    from odf.services.scheduler import schedule, unschedule
    if status == 1:
        schedule(session, flow_id)
    else:
        unschedule(flow_id)


def apply(session, change_id: int, approval_token: str) -> ChangeRequest:
    c = session.get(ChangeRequest, change_id)
    if not c:
        raise ValueError("change not found")
    if not verify_token(int(c.target), c.action, approval_token):
        raise PermissionError("approval required")

    if c.action == "run_flow":
        from odf.services.jobs import enqueue
        _flow(session, int(c.target), c.project_id)
        enqueue(session, int(c.target))
    elif c.action == "pause_flow":
        _set_flow_status(session, int(c.target), 0, c.project_id)
    elif c.action == "resume_flow":
        _set_flow_status(session, int(c.target), 1, c.project_id)
    elif c.action == "rollback_flow":
        f = _flow(session, int(c.target), c.project_id)
        f.current_version = int(c.payload_json["version"])
        session.commit()
    elif c.action == "publish_interface":
        i = session.get(Interface, int(c.target))
        if not i or i.project_id != c.project_id:
            raise ValueError("interface not found")
        i.status = 1
        session.commit()
    elif c.action == "revoke_interface":
        i = session.get(Interface, int(c.target))
        if not i or i.project_id != c.project_id:
            raise ValueError("interface not found")
        i.status = 0
        session.commit()
    elif c.action in ("publish_pipeline", "pause_pipeline",
                      "resume_pipeline", "rollback_pipeline"):
        from odf.assets.service import publish_asset, rollback_asset
        from odf.models import Asset
        a = session.get(Asset, int(c.target))
        if not a or a.type != "pipeline" or a.project_id != c.project_id:
            raise ValueError("pipeline not found")
        if c.action == "publish_pipeline":
            publish_asset(session, a.id, c.actor)
        elif c.action == "pause_pipeline":
            a.enabled = False
            session.commit()
        elif c.action == "resume_pipeline":
            a.enabled = True
            session.commit()
        else:
            rollback_asset(session, a.id,
                           int(c.payload_json["version"]), c.actor)
    elif c.action in ("publish_api", "rollback_api", "enable_api",
                      "revoke_api"):
        from odf.assets.service import publish_asset, rollback_asset
        from odf.models import Asset
        a = session.get(Asset, int(c.target))
        if not a or a.type != "api" or a.project_id != c.project_id:
            raise ValueError("API not found")
        if c.action == "publish_api":
            publish_asset(session, a.id, c.actor)
            a.enabled = True
            session.commit()
        elif c.action == "rollback_api":
            rollback_asset(session, a.id,
                           int(c.payload_json["version"]), c.actor)
            a.enabled = True
            session.commit()
        elif c.action == "enable_api":
            if not a.published_version_id:
                raise ValueError("API is not published")
            a.enabled = True
            session.commit()
        else:
            a.enabled = False
            session.commit()
    elif c.action in ("publish_dataset", "rollback_dataset",
                      "publish_metric", "rollback_metric"):
        from odf.assets.service import publish_asset, rollback_asset
        from odf.models import Asset
        a = session.get(Asset, int(c.target))
        expected = "dataset" if c.action.endswith("dataset") else "metric"
        if not a or a.type != expected or a.project_id != c.project_id:
            raise ValueError("%s not found" % expected)
        if c.action.startswith("publish"):
            publish_asset(session, a.id, c.actor)
        else:
            rollback_asset(session, a.id,
                           int(c.payload_json["version"]), c.actor)
    elif c.action in ("publish_dashboard", "rollback_dashboard"):
        from odf.assets.service import publish_asset, rollback_asset
        from odf.models import Asset
        a = session.get(Asset, int(c.target))
        if not a or a.type != "dashboard" or \
                a.project_id != c.project_id:
            raise ValueError("dashboard not found")
        if c.action == "publish_dashboard":
            publish_asset(session, a.id, c.actor)
        else:
            rollback_asset(session, a.id,
                           int(c.payload_json["version"]), c.actor)
    elif c.action in ("publish_app", "rollback_app"):
        from odf.assets.service import publish_asset, rollback_asset
        from odf.models import Asset
        a = session.get(Asset, int(c.target))
        if not a or a.type != "app" or a.project_id != c.project_id:
            raise ValueError("app not found")
        if c.action == "publish_app":
            publish_asset(session, a.id, c.actor)
        else:
            rollback_asset(session, a.id,
                           int(c.payload_json["version"]), c.actor)
    else:
        raise ValueError("unsupported action: %s" % c.action)

    write_audit(session, c.actor, c.action, c.target, c.payload_json)
    c.status = "applied"
    c.applied_at = datetime.now(timezone.utc)
    session.commit()
    return c
