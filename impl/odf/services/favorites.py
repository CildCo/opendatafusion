from odf.models import Asset, Dataset, Datasource, Favorite

ASSET_TYPES = ("dataset", "metric", "model", "pipeline", "api", "dashboard",
               "app")
OBJECT_TYPES = ASSET_TYPES + ("table",)

ROUTES = {
    "dataset": "/datasets/%d",
    "metric": "/metrics/%d",
    "model": "/models/%d",
    "pipeline": "/pipelines/%d",
    "api": "/apis/%d",
    "dashboard": "/dashboards/%d/run",
    "app": "/apps/%d/run",
    "table": "/catalog/%d",
}


def _asset(session, project_id, object_type, object_id):
    a = session.get(Asset, object_id)
    if not a or a.type != object_type or a.project_id != project_id:
        raise ValueError("favorite target not found")
    return a


def _table(session, project_id, object_id):
    d = session.get(Dataset, object_id)
    ds = session.get(Datasource, d.datasource_id) if d else None
    if not d or not ds or ds.project_id != project_id:
        raise ValueError("favorite target not found")
    return d, ds


def _item(session, row):
    if row.object_type == "table":
        d = session.get(Dataset, row.object_id)
        ds = session.get(Datasource, d.datasource_id) if d else None
        if not d:
            return None
        return {"id": row.id, "object_type": "table",
                "object_id": d.id, "type": "table",
                "label": "%s.%s" % (d.schema_name, d.table_name),
                "sub": ds.name if ds else "",
                "route": ROUTES["table"] % d.id,
                "created_at": row.created_at.isoformat()}
    a = session.get(Asset, row.object_id)
    if not a or a.type != row.object_type:
        return None
    return {"id": row.id, "object_type": row.object_type,
            "object_id": a.id, "type": a.type, "label": a.name,
            "sub": a.key, "route": ROUTES[a.type] % a.id,
            "created_at": row.created_at.isoformat()}


def _check(session, project_id, object_type, object_id):
    if object_type not in OBJECT_TYPES:
        raise ValueError("unsupported favorite type")
    if object_type == "table":
        _table(session, project_id, object_id)
    else:
        _asset(session, project_id, object_type, object_id)


def list_favorites(session, project_id: int, user_id: int,
                   object_type: str | None = None):
    q = (session.query(Favorite)
         .filter_by(project_id=project_id, user_id=user_id))
    if object_type:
        q = q.filter_by(object_type=object_type)
    out = []
    for row in q.order_by(Favorite.created_at.desc(),
                          Favorite.id.desc()).all():
        item = _item(session, row)
        if item:
            out.append(item)
    return out


def is_favorite(session, project_id: int, user_id: int, object_type: str,
                object_id: int) -> bool:
    return bool(session.query(Favorite).filter_by(
        project_id=project_id, user_id=user_id, object_type=object_type,
        object_id=object_id).first())


def add_favorite(session, project_id: int, user_id: int, object_type: str,
                 object_id: int):
    _check(session, project_id, object_type, object_id)
    row = session.query(Favorite).filter_by(
        project_id=project_id, user_id=user_id, object_type=object_type,
        object_id=object_id).first()
    if not row:
        row = Favorite(project_id=project_id, user_id=user_id,
                       object_type=object_type, object_id=object_id)
        session.add(row)
        session.commit()
        session.refresh(row)
    return _item(session, row)


def remove_favorite(session, project_id: int, user_id: int,
                    object_type: str, object_id: int) -> bool:
    row = session.query(Favorite).filter_by(
        project_id=project_id, user_id=user_id, object_type=object_type,
        object_id=object_id).first()
    if not row:
        return False
    session.delete(row)
    session.commit()
    return True
