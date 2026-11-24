import re
import time

from sqlalchemy import func

from odf.models import (AuditLog, Column, Dataset, DatasetTag, Datasource,
                        LineageEdge, QualityResult, QualityRule, Tag)
from odf.services.audit import write_audit
from odf.services.masking import apply_masks
from odf.services.query import execute_query
from odf.services.sqldialect import limited

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def create_tag(session, project_id: int, name: str) -> Tag:
    t = Tag(project_id=project_id, name=name)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def list_tags(session, project_id: int):
    return session.query(Tag).filter_by(project_id=project_id).order_by(Tag.id).all()


def tag_dataset(session, dataset_id: int, tag_id: int,
                project_id: int | None = None) -> DatasetTag:
    d = session.get(Dataset, dataset_id)
    t = session.get(Tag, tag_id)
    if not d or not t:
        raise ValueError("dataset or tag not found")
    if project_id is not None:
        ds = session.get(Datasource, d.datasource_id)
        if not ds or ds.project_id != project_id or t.project_id != project_id:
            raise ValueError("dataset or tag is outside the project")
    row = (session.query(DatasetTag)
           .filter_by(dataset_id=dataset_id, tag_id=tag_id).first())
    if row:
        return row
    row = DatasetTag(dataset_id=dataset_id, tag_id=tag_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def untag_dataset(session, dataset_id: int, tag_id: int,
                  project_id: int | None = None) -> bool:
    q = session.query(DatasetTag).filter_by(dataset_id=dataset_id,
                                            tag_id=tag_id)
    row = q.first()
    if not row:
        return False
    if project_id is not None:
        d = session.get(Dataset, dataset_id)
        ds = session.get(Datasource, d.datasource_id) if d else None
        t = session.get(Tag, tag_id)
        if (not ds or ds.project_id != project_id
                or not t or t.project_id != project_id):
            raise ValueError("dataset or tag is outside the project")
    q.delete()
    session.commit()
    return True


def list_datasets(session, project_id: int | None = None):
    q = (session.query(Dataset)
         .join(Datasource, Dataset.datasource_id == Datasource.id))
    if project_id is not None:
        q = q.filter(Datasource.project_id == project_id)
    return [{"id": d.id, "datasource_id": d.datasource_id,
             "schema": d.schema_name, "table": d.table_name}
            for d in q.order_by(Dataset.id).all()]


def _dataset_in_project(session, dataset_id: int,
                        project_id: int | None = None):
    d = session.get(Dataset, dataset_id)
    if not d:
        return None, None
    ds = session.get(Datasource, d.datasource_id)
    if project_id is not None and (not ds or ds.project_id != project_id):
        return None, None
    return d, ds


def _dataset_stats(session, dataset_id: int, column_count: int):
    rules = (session.query(QualityRule)
             .filter_by(dataset_id=dataset_id).all())
    latest = None
    if rules:
        row = (session.query(QualityResult)
               .filter(QualityResult.rule_id.in_([r.id for r in rules]))
               .order_by(QualityResult.at.desc(),
                         QualityResult.id.desc()).first())
        if row:
            latest = {"status": row.status, "at": row.at.isoformat()}
    last_activity = (session.query(func.max(AuditLog.at))
                     .filter(AuditLog.target == str(dataset_id)).scalar())
    return {"column_count": column_count, "rule_count": len(rules),
            "last_quality": latest,
            "last_activity_at": (last_activity.isoformat()
                                 if last_activity else None)}


def dataset_detail(session, dataset_id: int, project_id: int | None = None):
    d, ds = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        return None
    cols = (session.query(Column).filter_by(dataset_id=dataset_id)
            .order_by(Column.id).all())
    tags = (session.query(Tag)
            .join(DatasetTag, DatasetTag.tag_id == Tag.id)
            .filter(DatasetTag.dataset_id == dataset_id).all())
    try:
        from odf.modelstudio.service import metrics_for_dataset
        owner = project_id if project_id is not None else ds.project_id
        related = metrics_for_dataset(session, owner, dataset_id)
    except Exception:
        related = []
    return {"id": d.id, "datasource_id": d.datasource_id,
            "datasource_name": ds.name if ds else None,
            "datasource_kind": ds.kind if ds else None,
            "project_id": ds.project_id if ds else None,
            "schema": d.schema_name, "table": d.table_name,
            "columns": [{"name": c.name, "type": c.data_type} for c in cols],
            "tags": [t.name for t in tags],
            "metrics": related,
            "stats": _dataset_stats(session, dataset_id, len(cols))}


def _qualified(d: Dataset) -> str:
    if not _IDENTIFIER.match(d.table_name or ""):
        raise ValueError("preview is not available for this table name")
    if d.schema_name:
        if not _IDENTIFIER.match(d.schema_name):
            raise ValueError("preview is not available for this schema name")
        return "%s.%s" % (d.schema_name, d.table_name)
    return d.table_name


def dataset_sample(session, project_id: int, dataset_id: int, limit: int = 20,
                   role: str | None = None, actor: str = ""):
    d, ds = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    try:
        max_rows = max(1, min(int(limit or 20), 200))
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")
    sql = "SELECT * FROM %s" % _qualified(d)
    started = time.time()
    try:
        result = execute_query(session, ds, limited(sql, ds.kind, max_rows + 1),
                               None, max_rows + 1, read_only=True)
    except ValueError as error:
        raise ValueError(str(error))
    rows = result["rows"]
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    cols = (session.query(Column).filter_by(dataset_id=dataset_id)
            .order_by(Column.id).all())
    content = {"query": {
        "datasource_id": ds.id,
        "table": "%s.%s" % (d.schema_name, d.table_name),
        "select": [{"column": c.name} for c in cols],
    }}
    rows = apply_masks(session, content, rows, role)
    elapsed = int((time.time() - started) * 1000)
    write_audit(session, actor, "dataset_sample", str(d.id),
                {"row_count": len(rows), "limit": max_rows})
    return {"columns": result["columns"], "rows": rows,
            "row_count": len(rows), "ms": elapsed, "truncated": truncated}


_DATASET_ACTIONS = ("dataset_sample", "set_column_policy",
                    "delete_column_policy", "create_row_policy",
                    "delete_row_policy")


def dataset_history(session, project_id: int, dataset_id: int,
                    limit: int = 50):
    d, _ = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    try:
        size = max(1, min(int(limit or 50), 200))
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")
    # Audit targets are plain ids shared by several object types, so the
    # action list keeps another object's history out of this dataset's.
    rows = (session.query(AuditLog)
            .filter(AuditLog.target.in_([str(dataset_id),
                                         "dataset:%d" % dataset_id]),
                    AuditLog.action.in_(_DATASET_ACTIONS))
            .order_by(AuditLog.at.desc(), AuditLog.id.desc())
            .limit(size).all())
    return [{"id": r.id, "actor": r.actor, "action": r.action,
             "at": r.at.isoformat(), "detail": r.detail_json or {}}
            for r in rows]


def search_catalog(session, project_id: int, q: str, limit: int = 50):
    text = (q or "").strip().lower()
    if not text:
        return {"tables": [], "columns": []}
    value = "%" + text + "%"
    limit = max(1, min(int(limit), 200))
    base = (session.query(Dataset, Datasource)
            .join(Datasource, Dataset.datasource_id == Datasource.id)
            .filter(Datasource.project_id == project_id))
    table_rows = (base
                  .filter(func.lower(Dataset.table_name).like(value))
                  .order_by(Dataset.id).limit(limit).all())
    col_rows = (session.query(Dataset, Datasource, Column)
                .join(Datasource, Dataset.datasource_id == Datasource.id)
                .join(Column, Column.dataset_id == Dataset.id)
                .filter(Datasource.project_id == project_id,
                        func.lower(Column.name).like(value))
                .order_by(Dataset.id, Column.id).limit(limit * 5).all())
    tables = [{"id": d.id, "datasource_id": d.datasource_id,
               "schema": d.schema_name, "table": d.table_name,
               "matched_columns": []} for d, _ in table_rows]
    columns = [{"dataset_id": d.id, "datasource_id": d.datasource_id,
                "schema": d.schema_name, "table": d.table_name,
                "column": c.name, "type": c.data_type}
               for d, _, c in col_rows][:limit]
    return {"tables": tables, "columns": columns}


def impact(session, project_id: int, ref: str, depth: int = 5):
    depth = max(1, min(int(depth), 20))
    queue = [(ref, 0)]
    seen = {ref}
    edges = []
    while queue:
        current, level = queue.pop(0)
        if level >= depth:
            continue
        rows = (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.from_ref == current,
                        LineageEdge.from_column.is_(None)).all())
        for row in rows:
            edges.append({"from": row.from_ref, "to": row.to_ref,
                          "from_type": row.from_type,
                          "to_type": row.to_type,
                          "to_id": row.to_id})
            if row.to_ref not in seen:
                seen.add(row.to_ref)
                queue.append((row.to_ref, level + 1))
    column_edges = []
    if seen:
        for row in (session.query(LineageEdge)
                    .filter(LineageEdge.project_id == project_id,
                            LineageEdge.from_column.isnot(None),
                            LineageEdge.from_ref.in_(seen)).all()):
            column_edges.append({
                "from": row.from_ref, "from_column": row.from_column,
                "to": row.to_ref, "to_column": row.to_column})
    return {"ref": ref, "nodes": sorted(seen), "edges": edges,
            "column_edges": column_edges}


def lineage(session, project_id: int):
    edges, seen = [], set()
    for row in (session.query(LineageEdge)
                .filter_by(project_id=project_id, from_column=None).all()):
        key = (row.from_ref, row.to_ref)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from": row.from_ref, "to": row.to_ref,
                      "asset_id": row.to_id})
    column_edges = []
    for row in (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.from_column.isnot(None)).all()):
        column_edges.append({
            "from": row.from_ref, "from_column": row.from_column,
            "to": row.to_ref, "to_column": row.to_column,
            "asset_id": row.to_id})
    nodes = sorted({e["from"] for e in edges} | {e["to"] for e in edges})
    return {"nodes": nodes, "edges": edges,
            "column_edges": column_edges}


_PROFILE_SKIP = ("blob", "binary", "bytea", "clob", "json", "xml", "array",
                 "map", "struct", "geometry", "geography")


def dataset_profile(session, project_id, dataset_id, sample=50000,
                    role=None, actor=""):
    d, ds = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    try:
        size = max(100, min(int(sample or 50000), 200000))
    except (TypeError, ValueError):
        raise ValueError("sample must be a number")
    cols = (session.query(Column).filter_by(dataset_id=dataset_id)
            .order_by(Column.id).all())
    usable = [c for c in cols if _IDENTIFIER.match(c.name or "")]
    from odf.services.masking import masks_for_target
    masks = masks_for_target(session, ds.id, d.schema_name, d.table_name,
                             role)

    def value(row, key):
        for name in row:
            if name.lower() == key.lower():
                return row[name]
        return None

    parts = ["COUNT(*) AS odf_rows"]
    for index, column in enumerate(usable):
        name = column.name
        parts.append("COUNT(%s) AS odf_c%d" % (name, index))
        parts.append("COUNT(DISTINCT %s) AS odf_d%d" % (name, index))
        kind = (column.data_type or "").lower()
        if not any(token in kind for token in _PROFILE_SKIP):
            parts.append("MIN(%s) AS odf_min%d" % (name, index))
            parts.append("MAX(%s) AS odf_max%d" % (name, index))
    inner = limited("SELECT * FROM %s" % _qualified(d), ds.kind, size)
    sql = "SELECT %s FROM (%s) odf_src" % (", ".join(parts), inner)
    started = time.time()
    result = execute_query(session, ds, sql, None, 1, read_only=True)
    row = result["rows"][0] if result["rows"] else {}
    total = int(value(row, "odf_rows") or 0)
    out = []
    for index, column in enumerate(usable):
        non_null = int(value(row, "odf_c%d" % index) or 0)
        masked = column.name in masks
        out.append({
            "name": column.name,
            "type": column.data_type,
            "nulls": max(total - non_null, 0),
            "null_ratio": round((total - non_null) * 100.0 / total, 1)
            if total else 0.0,
            "distinct": int(value(row, "odf_d%d" % index) or 0),
            "min": None if masked else value(row, "odf_min%d" % index),
            "max": None if masked else value(row, "odf_max%d" % index),
            "masked": masked,
        })
    skipped = [c.name for c in cols if c not in usable]
    write_audit(session, actor, "profile_dataset", str(dataset_id),
                {"sample": size, "rows": total})
    return {"rows": total, "sample": size,
            "ms": int((time.time() - started) * 1000),
            "columns": out, "skipped_columns": skipped}
