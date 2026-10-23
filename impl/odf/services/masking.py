import hashlib

from odf.apistudio.catalog import table_columns
from odf.assets.service import get_asset
from odf.models import AssetVersion, ColumnPolicy, Dataset, Datasource
from odf.services.audit import write_audit

CLASSIFICATIONS = {"pii", "confidential", "sensitive"}
MASK_TYPES = {"redact", "partial", "hash", "null"}
ROLES = {"viewer", "editor", "approver", "admin"}


def _dataset(session, project_id, dataset_id):
    a = get_asset(session, dataset_id)
    if not a or a.type != "dataset" or a.project_id != project_id:
        raise ValueError("dataset not found")
    vid = a.published_version_id or a.draft_version_id
    v = session.get(AssetVersion, vid) if vid else None
    if not v:
        raise ValueError("dataset content not found")
    q = v.content_json.get("query") or {}
    table = q.get("table") or ""
    name = table.split(".")[-1] if table else ""
    ds = session.get(Datasource, q.get("datasource_id"))
    if not ds or ds.project_id != project_id:
        raise ValueError("dataset datasource not found")
    d = (session.query(Dataset)
         .filter_by(datasource_id=ds.id, table_name=name).first())
    if not d:
        raise ValueError("dataset metadata not found; sync the datasource")
    return a, d, ds


def _out(p):
    return {"id": p.id, "dataset_id": None, "column": p.column_name,
            "classification": p.classification, "mask_type": p.mask_type,
            "exempt_roles": p.exempt_roles_json or [],
            "datasource_id": p.datasource_id,
            "schema": p.schema_name, "table": p.table_name,
            "created_by": p.created_by, "created_at": p.created_at}


def create_column_policy(session, project_id, dataset_id, column,
                         classification, mask_type, exempt_roles, actor):
    if classification not in CLASSIFICATIONS:
        raise ValueError("invalid classification")
    if mask_type not in MASK_TYPES:
        raise ValueError("invalid mask type")
    if not isinstance(exempt_roles, list) or any(
            not isinstance(r, str) or r not in ROLES for r in exempt_roles):
        raise ValueError("invalid exempt roles")
    a, d, ds = _dataset(session, project_id, dataset_id)
    if column not in table_columns(session, ds, d.table_name):
        raise ValueError("column not in dataset table")
    p = (session.query(ColumnPolicy)
         .filter_by(datasource_id=ds.id, schema_name=d.schema_name or "",
                    table_name=d.table_name, column_name=column).first())
    if not p:
        p = ColumnPolicy(project_id=project_id, datasource_id=ds.id,
                         schema_name=d.schema_name or "",
                         table_name=d.table_name, column_name=column,
                         created_by=actor)
        session.add(p)
    p.classification = classification
    p.mask_type = mask_type
    p.exempt_roles_json = list(dict.fromkeys(exempt_roles))
    session.commit()
    session.refresh(p)
    out = _out(p)
    out["dataset_id"] = dataset_id
    write_audit(session, actor, "set_column_policy", str(dataset_id),
                {"column": column, "classification": classification,
                 "mask_type": mask_type})
    return out


def list_column_policies(session, project_id, dataset_id):
    _, d, ds = _dataset(session, project_id, dataset_id)
    rows = (session.query(ColumnPolicy)
            .filter_by(datasource_id=ds.id, schema_name=d.schema_name or "",
                       table_name=d.table_name)
            .order_by(ColumnPolicy.column_name).all())
    out = []
    for p in rows:
        item = _out(p)
        item["dataset_id"] = dataset_id
        out.append(item)
    return out


def delete_column_policy(session, project_id, dataset_id, policy_id, actor):
    _, d, ds = _dataset(session, project_id, dataset_id)
    p = session.get(ColumnPolicy, policy_id)
    if not p or p.project_id != project_id or p.datasource_id != ds.id or \
            p.table_name != d.table_name:
        raise ValueError("column policy not found")
    session.delete(p)
    session.commit()
    write_audit(session, actor, "delete_column_policy", str(dataset_id),
                {"policy_id": policy_id, "column": p.column_name})
    return {"deleted": True}


def datasource_has_policies(session, datasource_id) -> bool:
    return (session.query(ColumnPolicy)
            .filter_by(datasource_id=datasource_id).first()) is not None


def output_source_map(content) -> dict:
    out = {}
    for item in (content.get("query") or {}).get("select") or []:
        if isinstance(item, dict) and item.get("column"):
            out[item.get("as") or item["column"]] = item["column"]
    return out


def _target(session, content):
    q = content.get("query") or {}
    ds = session.get(Datasource, q.get("datasource_id"))
    table = q.get("table")
    if not ds or not table:
        return None, "", table or ""
    name = table.split(".")[-1]
    schema = table.split(".", 1)[0] if "." in table else ""
    row = (session.query(Dataset)
           .filter_by(datasource_id=ds.id, table_name=name).first())
    if row:
        schema = row.schema_name or ""
    return ds, schema, name


def masks_for_target(session, datasource_id, schema, table, role):
    if role == "admin":
        return {}
    rows = (session.query(ColumnPolicy)
            .filter_by(datasource_id=datasource_id, schema_name=schema or "",
                       table_name=table).all())
    out = {}
    for p in rows:
        if p.classification not in CLASSIFICATIONS:
            continue
        if role and role in (p.exempt_roles_json or []):
            continue
        out[p.column_name] = p.mask_type
    return out


def mask_value(value, mask_type):
    if value is None:
        return None
    if mask_type == "null":
        return None
    if mask_type == "redact":
        return "***"
    if mask_type == "hash":
        return "sha256:" + hashlib.sha256(
            str(value).encode("utf-8")).hexdigest()[:16]
    text = str(value)
    if len(text) <= 2:
        return "**"
    if len(text) <= 6:
        return text[0] + "*" * (len(text) - 2) + text[-1]
    return text[:2] + "*" * (len(text) - 4) + text[-2:]


def apply_masks(session, content, rows, role):
    ds, schema, table = _target(session, content)
    if not ds:
        return rows
    masks = masks_for_target(session, ds.id, schema, table, role)
    if not masks:
        return rows
    mapping = output_source_map(content)
    out = []
    for row in rows:
        item = dict(row)
        for output, source in mapping.items():
            if source in masks and output in item:
                item[output] = mask_value(item[output], masks[source])
        out.append(item)
    return out


def apply_metric_masks(session, ds_content, rows, dims, measure_alias,
                       measure_source, role):
    ds, schema, table = _target(session, ds_content)
    if not ds:
        return rows
    masks = masks_for_target(session, ds.id, schema, table, role)
    if not masks:
        return rows
    mapping = output_source_map(ds_content)
    out = []
    for row in rows:
        item = dict(row)
        for dim in dims:
            source = mapping.get(dim)
            if source in masks and dim in item:
                item[dim] = mask_value(item[dim], masks[source])
        physical = mapping.get(measure_source, measure_source)
        if measure_alias and physical in masks:
            item[measure_alias] = mask_value(item[measure_alias],
                                             masks[physical])
        out.append(item)
    return out
