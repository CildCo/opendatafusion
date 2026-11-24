import json
from datetime import datetime, timezone

from odf.models import (Asset, Column, Dataset, DatasetTag, Datasource,
                        LineageEdge, Project, QualityRule, Tag)
from odf.services.platform import get_doc
from odf.settings import get_settings

FORMAT = "odf-catalog"
VERSION = 1


def _now():
    return datetime.now(timezone.utc)


def _project(session, project):
    datasets = []
    rows = (session.query(Dataset).join(
        Datasource, Dataset.datasource_id == Datasource.id)
        .filter(Datasource.project_id == project.id)
        .order_by(Dataset.id).all())
    for row in rows:
        datasource = session.get(Datasource, row.datasource_id)
        columns = (session.query(Column).filter_by(dataset_id=row.id)
                   .order_by(Column.id).all())
        tag_ids = [t.tag_id for t in session.query(DatasetTag)
                   .filter_by(dataset_id=row.id).all()]
        tags = [t.name for t in session.query(Tag)
                .filter(Tag.id.in_(tag_ids or [0])).all()] if tag_ids else []
        rules = (session.query(QualityRule).filter_by(dataset_id=row.id).all())
        datasets.append({
            "datasource": {"id": datasource.id, "name": datasource.name,
                           "kind": datasource.kind},
            "schema": row.schema_name, "table": row.table_name,
            "domain_id": row.domain_id, "tags": tags,
            "columns": [{"name": c.name, "type": c.data_type}
                        for c in columns],
            "quality_rules": [{"name": r.name, "kind": r.kind,
                               "column": r.column_name,
                               "enabled": bool(r.enabled)}
                              for r in rules],
        })
    assets = []
    for row in (session.query(Asset).filter_by(project_id=project.id)
                .order_by(Asset.id).all()):
        assets.append({"type": row.type, "key": row.key, "name": row.name,
                       "owner": row.owner, "domain_id": row.domain_id,
                       "description": row.description,
                       "published": row.published_version_id is not None,
                       "enabled": bool(row.enabled)})
    edges = []
    for row in (session.query(LineageEdge)
                .filter_by(project_id=project.id).all()):
        edges.append({"from": row.from_ref, "from_column": row.from_column,
                      "to": row.to_ref, "to_column": row.to_column})
    return {"code": project.code, "name": project.name,
            "environment": project.environment,
            "datasets": datasets, "assets": assets, "lineage": edges}


def export_all(session):
    projects = []
    for project in session.query(Project).order_by(Project.id).all():
        projects.append(_project(session, project))
    return {"format": FORMAT, "version": VERSION,
            "generated_at": _now().isoformat(), "projects": projects}


def export_project(session, project_id):
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("project not found")
    return {"format": FORMAT, "version": VERSION,
            "generated_at": _now().isoformat(),
            "projects": [_project(session, project)]}


def _post(url, token, payload):
    from odf.services.net import request
    body = json.dumps(payload, ensure_ascii=False, default=str).encode(
        "utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    code, _, _ = request(
        url, method="POST", body=body, headers=headers, timeout=20,
        allow_private=get_settings().http_allow_private,
        max_bytes=1024 * 1024)
    if code >= 400:
        raise ValueError("catalog endpoint answered HTTP %d" % code)


def push(session):
    config = get_doc(session, mask=False).get("lineage") or {}
    url = (config.get("catalog_sync_url") or "").strip()
    if not url:
        raise ValueError("catalog sync endpoint is not configured")
    payload = export_all(session)
    try:
        _post(url, config.get("catalog_sync_token"), payload)
    except Exception as error:
        _mark(session, 0, str(error)[:300])
        raise
    _mark(session, len(payload["projects"]))
    return {"projects": len(payload["projects"])}


def _mark(session, count, error=None):
    from odf.models import PlatformSetting
    row = session.get(PlatformSetting, 1)
    if not row:
        return
    data = dict(row.settings_json or {})
    lineage = dict(data.get("lineage") or {})
    lineage["catalog_last_sync_at"] = _now().isoformat()
    lineage["catalog_last_sync_projects"] = count
    if error:
        lineage["catalog_last_sync_error"] = error
    else:
        lineage.pop("catalog_last_sync_error", None)
    data["lineage"] = lineage
    row.settings_json = data
    session.commit()


def due(session, now=None):
    config = get_doc(session, mask=False).get("lineage") or {}
    interval = int(config.get("catalog_sync_interval_minutes") or 0)
    if interval <= 0 or not (config.get("catalog_sync_url") or "").strip():
        return False
    last = config.get("catalog_last_sync_at")
    if not last:
        return True
    try:
        stamp = datetime.fromisoformat(last)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (_now() - stamp).total_seconds() >= interval * 60
