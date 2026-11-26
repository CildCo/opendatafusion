from odf.apistudio.catalog import table_columns
from odf.apistudio.compiler import OPS
from odf.assets.service import get_asset
from odf.models import AssetVersion, Datasource, RowPolicy
from odf.services.audit import write_audit

ROLES = {"viewer", "editor", "approver", "admin"}


def _dataset(session, project_id, dataset_id):
    a = get_asset(session, dataset_id)
    if not a or a.type != "dataset" or a.project_id != project_id:
        raise ValueError("dataset not found")
    return a


def _content(session, asset):
    vid = asset.published_version_id or asset.draft_version_id
    v = session.get(AssetVersion, vid) if vid else None
    if not v:
        raise ValueError("dataset content not found")
    return v.content_json


def _physical_columns(session, content):
    q = content.get("query") or {}
    ds = session.get(Datasource, q.get("datasource_id"))
    if not ds or not q.get("table"):
        raise ValueError("dataset table not found")
    return table_columns(session, ds, q["table"])


def _validate(session, content, column, op, value, roles):
    if column not in _physical_columns(session, content):
        raise ValueError("column not in dataset table")
    if op not in OPS:
        raise ValueError("unsupported operator")
    if not isinstance(roles, list) or \
            any(not isinstance(r, str) or r not in ROLES for r in roles):
        raise ValueError("invalid roles")
    if len(set(roles)) != len(roles):
        raise ValueError("duplicate roles")
    if op == "in":
        if not isinstance(value, list) or not value or len(value) > 100:
            raise ValueError("in requires 1..100 values")
    elif isinstance(value, (list, dict)) or value is None:
        raise ValueError("invalid policy value")


def _out(p):
    return {"id": p.id, "dataset_id": p.dataset_id, "column": p.column,
            "op": p.op, "value": p.value, "roles": p.roles or [],
            "created_by": p.created_by, "created_at": p.created_at}


def create_policy(session, project_id, dataset_id, column, op, value, roles,
                  actor):
    asset = _dataset(session, project_id, dataset_id)
    content = _content(session, asset)
    _validate(session, content, column, op, value, roles)
    p = RowPolicy(project_id=project_id, dataset_id=dataset_id,
                  column=column, op=op, value=value, roles=roles,
                  created_by=actor)
    session.add(p)
    session.commit()
    session.refresh(p)
    write_audit(session, actor, "create_row_policy", str(dataset_id),
                {"policy_id": p.id, "column": column, "op": op})
    return _out(p)


def list_policies(session, project_id, dataset_id):
    _dataset(session, project_id, dataset_id)
    return [_out(p) for p in session.query(RowPolicy)
            .filter_by(project_id=project_id, dataset_id=dataset_id)
            .order_by(RowPolicy.id).all()]


def delete_policy(session, project_id, dataset_id, policy_id, actor):
    _dataset(session, project_id, dataset_id)
    p = session.get(RowPolicy, policy_id)
    if not p or p.project_id != project_id or p.dataset_id != dataset_id:
        raise ValueError("policy not found")
    session.delete(p)
    session.commit()
    write_audit(session, actor, "delete_row_policy", str(dataset_id),
                {"policy_id": policy_id})
    return {"deleted": True}


def filters_for(session, dataset_id, role):
    if role == "admin":
        return []
    role = role or "viewer"
    rows = (session.query(RowPolicy).filter_by(dataset_id=dataset_id).all())
    out = []
    for p in rows:
        if p.roles and role not in p.roles:
            continue
        out.append({"column": p.column, "op": p.op, "value": p.value})
    return out


def dataset_asset_for_query(session, project_id, datasource_id, table):
    """Resolve the logical dataset asset behind a datasource/table query."""
    from odf.models import Asset, AssetVersion
    if not isinstance(datasource_id, int) or not isinstance(table, str):
        return None
    assets = (session.query(Asset)
              .filter(Asset.project_id == project_id,
                      Asset.type == "dataset").all())
    for asset in assets:
        vid = asset.published_version_id or asset.draft_version_id
        version = session.get(AssetVersion, vid) if vid else None
        content = (version.content_json or {}) if version else {}
        query = content.get("query") or {}
        if query.get("datasource_id") != datasource_id:
            continue
        name = query.get("table")
        if name == table or (isinstance(name, str)
                             and name.split(".")[-1] == table.split(".")[-1]):
            return asset
    return None


def datasource_has_row_policies(session, datasource_id):
    from odf.models import Asset, AssetVersion
    assets = (session.query(Asset)
              .filter(Asset.type == "dataset").all())
    ids = []
    for asset in assets:
        vid = asset.published_version_id or asset.draft_version_id
        version = session.get(AssetVersion, vid) if vid else None
        query = ((version.content_json or {}).get("query")
                 if version else None) or {}
        if query.get("datasource_id") == datasource_id:
            ids.append(asset.id)
    if not ids:
        return False
    return (session.query(RowPolicy)
            .filter(RowPolicy.dataset_id.in_(ids)).first()) is not None
