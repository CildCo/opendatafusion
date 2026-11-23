import secrets

from sqlalchemy import and_, or_

from odf.models import (ApiCallStat, Asset, AssetVersion, InterfaceGrant,
                        InterfaceRequest, Job, LineageEdge,
                        PipelineNodeRun, ShareLink)


def _next_version(session, asset_id):
    last = (session.query(AssetVersion).filter_by(asset_id=asset_id)
            .order_by(AssetVersion.version.desc()).first())
    return (last.version + 1) if last else 1


def create_asset(session, project_id, type, name, content, owner, key=None,
                 enabled=True):
    key = key or "%s_%s" % (type, secrets.token_hex(4))
    from odf.services.quota import check_asset
    check_asset(session, project_id)
    a = Asset(project_id=project_id, type=type, key=key, name=name,
              owner=owner, enabled=enabled)
    session.add(a)
    session.flush()
    v = AssetVersion(asset_id=a.id, version=1, content_json=content,
                     status="draft", created_by=owner)
    session.add(v)
    session.flush()
    a.draft_version_id = v.id
    session.commit()
    session.refresh(a)
    return a


def delete_asset_of(session, asset_id, project_id, kind):
    a = session.get(Asset, asset_id)
    if not a or a.type != kind or a.project_id != project_id:
        raise ValueError("%s not found" % kind)
    return delete_asset(session, asset_id, project_id)


def get_asset(session, asset_id):
    return session.get(Asset, asset_id)


def delete_asset(session, asset_id, project_id):
    """Remove an asset together with the rows that point at it."""
    a = session.get(Asset, asset_id)
    if not a or a.project_id != project_id:
        raise ValueError("asset not found")
    kind = a.type
    job_ids = [row[0] for row in
               session.query(Job.id).filter_by(asset_id=asset_id).all()]
    if job_ids:
        session.query(PipelineNodeRun).filter(
            PipelineNodeRun.job_id.in_(job_ids)).delete(
                synchronize_session=False)
        session.query(Job).filter(Job.asset_id == asset_id).delete(
            synchronize_session=False)
    for model, column in ((ShareLink, ShareLink.asset_id),
                          (InterfaceGrant, InterfaceGrant.interface_asset_id),
                          (InterfaceRequest, InterfaceRequest.interface_asset_id),
                          (ApiCallStat, ApiCallStat.api_id)):
        session.query(model).filter(column == asset_id).delete(
            synchronize_session=False)
    session.query(LineageEdge).filter(or_(
        LineageEdge.asset_id == asset_id,
        and_(LineageEdge.from_type == kind,
             LineageEdge.from_id == str(asset_id)),
        and_(LineageEdge.to_type == kind,
             LineageEdge.to_id == str(asset_id)),
    )).delete(synchronize_session=False)
    session.query(AssetVersion).filter_by(asset_id=asset_id).delete(
        synchronize_session=False)
    session.delete(a)
    session.commit()
    return kind


def list_assets(session, project_id, type=None):
    q = session.query(Asset).filter_by(project_id=project_id)
    if type:
        q = q.filter_by(type=type)
    return q.order_by(Asset.id).all()


def page_assets(session, project_id, type=None, page=1, page_size=50,
                q_text=None):
    from sqlalchemy import or_
    from odf.services.pagination import limits
    page, page_size = limits(page, page_size)
    q = session.query(Asset).filter_by(project_id=project_id)
    if type:
        q = q.filter_by(type=type)
    if q_text:
        like = "%%%s%%" % q_text
        q = q.filter(or_(Asset.name.ilike(like), Asset.key.ilike(like)))
    total = q.count()
    rows = (q.order_by(Asset.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return rows, total, page, page_size


class DraftConflict(ValueError):
    pass


def update_draft(session, asset_id, content, actor, note="",
                 base_version=None):
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    current = (session.get(AssetVersion, a.draft_version_id)
               if a.draft_version_id else None)
    if base_version is not None and (
            not current or current.version != int(base_version)):
        raise DraftConflict(
            "draft changed since version %s" % base_version)
    if a.type == "dataset" and content.get("mode") == "sql":
        from odf.modelstudio.content import derive_sql_columns
        try:
            content = {**content, "columns": derive_sql_columns(
                session, content, a.project_id)}
        except ValueError:
            content = {**content, "columns": []}
    v = AssetVersion(asset_id=asset_id, version=_next_version(session, asset_id),
                     content_json=content, status="draft",
                     created_by=actor, note=note)
    session.add(v)
    session.flush()
    a.draft_version_id = v.id
    session.commit()
    session.refresh(v)
    return v


def _validate_for(session, asset, content):
    if asset.type == "pipeline":
        from odf.pipeline.validate import validate_pipeline_content
        return validate_pipeline_content(session, content, asset.project_id)
    if asset.type == "api":
        from odf.apistudio.content import validate_content
        return validate_content(session, content, asset.project_id)
    if asset.type == "dataset":
        from odf.modelstudio.content import validate_dataset
        return validate_dataset(session, content, asset.project_id)
    if asset.type == "metric":
        from odf.modelstudio.content import validate_metric
        return validate_metric(session, content, asset.project_id)
    if asset.type == "dashboard":
        from odf.dashboards.content import validate_dashboard
        return validate_dashboard(session, content, asset.project_id)
    if asset.type == "app":
        from odf.appstudio.content import validate_app
        return validate_app(session, content, asset.project_id)
    return []


def publish_asset(session, asset_id, actor):
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    v = session.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    if not v:
        raise ValueError("draft not found")
    errs = _validate_for(session, a, v.content_json)
    if errs:
        raise ValueError("invalid content: %s" % errs)
    if a.published_version_id:
        old = session.get(AssetVersion, a.published_version_id)
        if old:
            old.status = "archived"
    v.status = "published"
    a.published_version_id = v.id
    if a.type == "api":
        a.enabled = True
    if a.type == "pipeline":
        from odf.pipeline.lineage import record_lineage
        record_lineage(session, a, v.content_json)
    session.commit()
    session.refresh(v)
    from odf.webhooks.service import emit_safe
    emit_safe(session, a.project_id, "asset.published",
              {"asset_id": a.id, "type": a.type, "key": a.key,
               "name": a.name, "version": v.version})
    from odf.services.notifications import notify
    notify(session, a.project_id, "publish",
           "%s 已发布：%s" % (ASSET_LABELS.get(a.type, a.type), a.name),
           "版本 v%d" % v.version, asset_link(a))
    return v


ASSET_LABELS = {"pipeline": "管道", "dataset": "数据集", "metric": "指标",
                "api": "API", "dashboard": "看板", "app": "应用"}


def asset_link(a):
    prefix = {"pipeline": "pipelines", "dataset": "datasets",
              "metric": "metrics", "api": "apis",
              "dashboard": "dashboards", "app": "apps"}.get(a.type)
    return "/%s/%d" % (prefix, a.id) if prefix else ""


def rollback_asset(session, asset_id, version, actor):
    a = session.get(Asset, asset_id)
    old = (session.query(AssetVersion)
           .filter_by(asset_id=asset_id, version=version).first())
    if not a or not old:
        raise ValueError("version not found")
    if old.status == "draft":
        raise ValueError("cannot rollback to a draft version")
    if a.type == "pipeline":
        from odf.pipeline.schema import validate_dag
        errs = validate_dag(old.content_json)
    else:
        errs = _validate_for(session, a, old.content_json)
    if errs:
        raise ValueError("invalid content: %s" % errs)
    if a.published_version_id:
        current = session.get(AssetVersion, a.published_version_id)
        if current:
            current.status = "archived"
    v = AssetVersion(asset_id=asset_id, version=_next_version(session, asset_id),
                     content_json=old.content_json, status="published",
                     created_by=actor, note="rollback to %s" % version)
    session.add(v)
    session.flush()
    a.published_version_id = v.id
    if a.type == "api":
        a.enabled = True
    if a.type == "pipeline":
        from odf.pipeline.lineage import record_lineage
        record_lineage(session, a, old.content_json)
    session.commit()
    session.refresh(v)
    from odf.webhooks.service import emit_safe
    emit_safe(session, a.project_id, "asset.rolled_back",
              {"asset_id": a.id, "type": a.type, "key": a.key,
               "name": a.name, "version": v.version})
    return v


def update_asset(session, asset_id, name=None, cron=None):
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    if name is not None:
        a.name = name
    if cron is not None:
        a.cron = cron or None
    session.commit()
    session.refresh(a)
    return a


def list_versions(session, asset_id):
    return (session.query(AssetVersion).filter_by(asset_id=asset_id)
            .order_by(AssetVersion.version.desc()).all())


def get_version(session, asset_id, version):
    return (session.query(AssetVersion)
            .filter_by(asset_id=asset_id, version=version).first())
