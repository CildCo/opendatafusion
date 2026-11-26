import re
import time

from sqlalchemy import func, or_

from odf.models import (AuditLog, CatalogComment, Column, ColumnPolicy,
                        ColumnTerm, Dataset, DatasetTag, Datasource, Domain,
                        GlossaryTerm, LineageEdge, QualityResult, QualityRule,
                        Tag)
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
    domains = {d.id: d for d in session.query(Domain).filter_by(
        project_id=project_id).all()} if project_id is not None else {}
    return [{"id": d.id, "datasource_id": d.datasource_id,
             "schema": d.schema_name, "table": d.table_name,
             "domain_id": d.domain_id,
             "domain_name": domains[d.domain_id].name
             if d.domain_id in domains else None}
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
    policies = {}
    if ds:
        for row in (session.query(ColumnPolicy)
                    .filter_by(datasource_id=d.datasource_id,
                               schema_name=d.schema_name,
                               table_name=d.table_name).all()):
            policies[row.column_name] = row
    domain = session.get(Domain, d.domain_id) if d.domain_id else None
    try:
        from odf.modelstudio.service import metrics_for_dataset
        owner = project_id if project_id is not None else ds.project_id
        related = metrics_for_dataset(session, owner, dataset_id)
    except Exception:
        related = []
    term_links = {}
    for link in (session.query(ColumnTerm, GlossaryTerm)
                 .join(GlossaryTerm, GlossaryTerm.id == ColumnTerm.term_id)
                 .filter(ColumnTerm.dataset_id == dataset_id).all()):
        term_links.setdefault(link[0].column_name, []).append(
            {"id": link[1].id, "term": link[1].term})
    open_comments = (session.query(CatalogComment)
                     .filter_by(dataset_id=dataset_id, status="open").count())
    all_comments = (session.query(CatalogComment)
                    .filter_by(dataset_id=dataset_id).count())
    return {"id": d.id, "datasource_id": d.datasource_id,
            "datasource_name": ds.name if ds else None,
            "datasource_kind": ds.kind if ds else None,
            "project_id": ds.project_id if ds else None,
            "schema": d.schema_name, "table": d.table_name,
            "domain_id": d.domain_id,
            "domain_name": domain.name if domain else None,
            "columns": [{
                "name": c.name, "type": c.data_type,
                "classification": policies[c.name].classification
                if c.name in policies else None,
                "mask_type": policies[c.name].mask_type
                if c.name in policies else None,
                "exempt_roles": policies[c.name].exempt_roles_json
                if c.name in policies else [],
                "terms": term_links.get(c.name, []),
            } for c in cols],
            "tags": [t.name for t in tags],
            "metrics": related,
            "comments": {"open": open_comments, "total": all_comments},
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
                    "delete_row_policy", "add_catalog_comment",
                    "resolve_catalog_comment")


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


def _comment(row):
    return {"id": row.id, "actor": row.actor, "body": row.body,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "resolved_at": (row.resolved_at.isoformat()
                            if row.resolved_at else None),
            "resolved_by": row.resolved_by}


def list_comments(session, project_id: int, dataset_id: int,
                  status: str | None = None, limit: int = 100):
    d, _ = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    q = session.query(CatalogComment).filter_by(dataset_id=dataset_id)
    if status in ("open", "resolved"):
        q = q.filter_by(status=status)
    try:
        size = max(1, min(int(limit or 100), 500))
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")
    return [_comment(row) for row in
            q.order_by(CatalogComment.created_at.desc(),
                       CatalogComment.id.desc()).limit(size).all()]


def add_comment(session, project_id: int, dataset_id: int, actor: str,
                body: str):
    d, _ = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    text = (body or "").strip()
    if not text:
        raise ValueError("comment body is required")
    if len(text) > 4000:
        raise ValueError("comment body is too long")
    row = CatalogComment(project_id=project_id, dataset_id=dataset_id,
                         actor=actor, body=text, status="open")
    session.add(row)
    session.commit()
    session.refresh(row)
    write_audit(session, actor, "add_catalog_comment", str(dataset_id),
                {"comment_id": row.id})
    return _comment(row)


def set_comment_status(session, project_id: int, comment_id: int,
                       actor: str, status: str):
    row = session.get(CatalogComment, comment_id)
    if not row or row.project_id != project_id:
        raise ValueError("comment not found")
    d, _ = _dataset_in_project(session, row.dataset_id, project_id)
    if not d:
        raise ValueError("comment not found")
    if status not in ("open", "resolved"):
        raise ValueError("status must be open or resolved")
    row.status = status
    if status == "resolved":
        from datetime import datetime, timezone
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by = actor
    else:
        row.resolved_at = None
        row.resolved_by = None
    session.commit()
    session.refresh(row)
    write_audit(session, actor, "resolve_catalog_comment",
                str(row.dataset_id), {"comment_id": row.id,
                                      "status": status})
    return _comment(row)


def link_column_term(session, project_id: int, dataset_id: int,
                     column: str, term_id: int, actor: str):
    d, _ = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    exists = (session.query(Column)
              .filter_by(dataset_id=dataset_id, name=column).first())
    if not exists:
        raise ValueError("column not found")
    term = session.get(GlossaryTerm, term_id)
    if not term or term.project_id != project_id:
        raise ValueError("term not found")
    row = session.query(ColumnTerm).filter_by(
        dataset_id=dataset_id, column_name=column, term_id=term_id).first()
    if not row:
        row = ColumnTerm(project_id=project_id, dataset_id=dataset_id,
                         column_name=column, term_id=term_id,
                         created_by=actor)
        session.add(row)
        session.commit()
        session.refresh(row)
    return {"id": row.id, "term_id": term_id, "term": term.term,
            "column": column}


def unlink_column_term(session, project_id: int, dataset_id: int,
                       column: str, term_id: int) -> bool:
    d, _ = _dataset_in_project(session, dataset_id, project_id)
    if not d:
        raise ValueError("dataset not found")
    row = session.query(ColumnTerm).filter_by(
        dataset_id=dataset_id, column_name=column, term_id=term_id).first()
    if not row:
        return False
    session.delete(row)
    session.commit()
    return True


def term_columns(session, project_id: int, term_id: int):
    term = session.get(GlossaryTerm, term_id)
    if not term or term.project_id != project_id:
        raise ValueError("term not found")
    out = []
    for link, dataset, datasource in (
            session.query(ColumnTerm, Dataset, Datasource)
            .join(Dataset, Dataset.id == ColumnTerm.dataset_id)
            .join(Datasource, Datasource.id == Dataset.datasource_id)
            .filter(ColumnTerm.term_id == term_id).all()):
        out.append({"dataset_id": dataset.id,
                    "datasource_id": datasource.id,
                    "schema": dataset.schema_name,
                    "table": dataset.table_name,
                    "column": link.column_name})
    return out


def search_catalog(session, project_id: int, q: str, limit: int = 50):
    text = (q or "").strip().lower()
    if not text:
        return {"tables": [], "columns": [], "tags": [], "terms": []}
    value = "%" + text + "%"
    limit = max(1, min(int(limit), 200))
    base = (session.query(Dataset, Datasource)
            .join(Datasource, Dataset.datasource_id == Datasource.id)
            .filter(Datasource.project_id == project_id))
    table_rows = (base
                  .filter(or_(func.lower(Dataset.table_name).like(value),
                              func.lower(Dataset.schema_name).like(value)))
                  .order_by(Dataset.id).limit(limit).all())
    tag_rows = (session.query(Tag)
                .filter(Tag.project_id == project_id,
                        func.lower(Tag.name).like(value)).all())
    term_rows = (session.query(GlossaryTerm)
                 .filter(GlossaryTerm.project_id == project_id,
                         func.lower(GlossaryTerm.term).like(value)).all())
    matched_terms = {}
    terms_by_id = {t.id: t.term for t in term_rows}
    if term_rows:
        term_links = (session.query(ColumnTerm, Dataset, Datasource)
                      .join(Dataset, Dataset.id == ColumnTerm.dataset_id)
                      .join(Datasource,
                            Datasource.id == Dataset.datasource_id)
                      .filter(Datasource.project_id == project_id,
                              ColumnTerm.term_id.in_(
                                  [t.id for t in term_rows])).all())
        known_terms = {d.id for d, _ in table_rows}
        for link, dataset, ds in term_links:
            matched_terms.setdefault(dataset.id, []).append(
                {"term": terms_by_id.get(link.term_id, ""),
                 "column": link.column_name})
            if dataset.id not in known_terms:
                table_rows.append((dataset, ds))
                known_terms.add(dataset.id)
    if tag_rows:
        tagged = (base.join(DatasetTag, DatasetTag.dataset_id == Dataset.id)
                  .filter(DatasetTag.tag_id.in_([t.id for t in tag_rows]))
                  .order_by(Dataset.id).limit(limit).all())
        known = {d.id for d, _ in table_rows}
        table_rows += [(d, ds) for d, ds in tagged if d.id not in known]
    ids = [d.id for d, _ in table_rows]
    matched_columns = {}
    if ids:
        for d_id, column in (session.query(Column.dataset_id, Column.name)
                             .filter(Column.dataset_id.in_(ids),
                                     func.lower(Column.name).like(value))
                             .all()):
            matched_columns.setdefault(d_id, []).append(column)
    matched_tags = {}
    if ids:
        for d_id, name in (session.query(DatasetTag.dataset_id, Tag.name)
                           .join(Tag, Tag.id == DatasetTag.tag_id)
                           .filter(DatasetTag.dataset_id.in_(ids)).all()):
            matched_tags.setdefault(d_id, []).append(name)
    col_rows = (session.query(Dataset, Datasource, Column)
                .join(Datasource, Dataset.datasource_id == Datasource.id)
                .join(Column, Column.dataset_id == Dataset.id)
                .filter(Datasource.project_id == project_id,
                        func.lower(Column.name).like(value))
                .order_by(Dataset.id, Column.id).limit(limit * 5).all())
    table_ids = {d.id for d, _ in table_rows}
    seen_cols = {}
    for d, ds, column in col_rows:
        seen_cols.setdefault(d.id, set()).add(column.name)
        if d.id not in table_ids:
            table_rows.append((d, ds))
            table_ids.add(d.id)
    for d_id, names in seen_cols.items():
        current = set(matched_columns.get(d_id, []))
        matched_columns[d_id] = sorted(current | names)
    table_rows = table_rows[:limit]
    tables = [{"id": d.id, "datasource_id": d.datasource_id,
               "datasource_name": ds.name,
               "schema": d.schema_name, "table": d.table_name,
               "matched_columns": matched_columns.get(d.id, []),
               "matched_tags": matched_tags.get(d.id, []),
               "matched_terms": matched_terms.get(d.id, [])}
              for d, ds in table_rows]
    columns = [{"dataset_id": d.id, "datasource_id": d.datasource_id,
                "datasource_name": ds.name,
                "schema": d.schema_name, "table": d.table_name,
                "column": c.name, "type": c.data_type}
               for d, ds, c in col_rows][:limit]
    return {"tables": tables, "columns": columns,
            "tags": [{"id": t.id, "name": t.name} for t in tag_rows],
            "terms": [{"id": t.id, "term": t.term} for t in term_rows]}


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


def lineage(session, project_id: int, ref: str | None = None,
            depth: int = 5, direction: str = "both"):
    try:
        depth = int(depth or 5)
    except (TypeError, ValueError):
        depth = 5
    depth = max(1, min(depth, 20))
    if direction not in ("upstream", "downstream", "both"):
        direction = "both"
    if ref:
        seen = {ref}
        queue = [(ref, 0)]
        found = {}
        while queue:
            current, level = queue.pop(0)
            if level >= depth:
                continue
            rows = []
            if direction in ("downstream", "both"):
                rows += (session.query(LineageEdge)
                         .filter(LineageEdge.project_id == project_id,
                                 LineageEdge.from_ref == current,
                                 LineageEdge.from_column.is_(None)).all())
            if direction in ("upstream", "both"):
                rows += (session.query(LineageEdge)
                         .filter(LineageEdge.project_id == project_id,
                                 LineageEdge.to_ref == current,
                                 LineageEdge.from_column.is_(None)).all())
            for row in rows:
                found[(row.from_ref, row.to_ref)] = row
                for node in (row.from_ref, row.to_ref):
                    if node not in seen:
                        seen.add(node)
                        queue.append((node, level + 1))
        edges = [{"from": row.from_ref, "to": row.to_ref,
                  "from_type": row.from_type, "to_type": row.to_type,
                  "asset_id": row.to_id}
                 for row in found.values()]
        column_edges = []
        for row in (session.query(LineageEdge)
                    .filter(LineageEdge.project_id == project_id,
                            LineageEdge.from_column.isnot(None),
                            LineageEdge.from_ref.in_(seen),
                            LineageEdge.to_ref.in_(seen)).all()):
            column_edges.append({
                "from": row.from_ref, "from_column": row.from_column,
                "to": row.to_ref, "to_column": row.to_column,
                "asset_id": row.to_id})
        node_types = {}
        for row in found.values():
            node_types[row.from_ref] = row.from_type
            node_types[row.to_ref] = row.to_type
        return {"ref": ref, "focus": ref, "direction": direction,
                "depth": depth, "nodes": sorted(seen),
                "node_types": node_types, "edges": edges,
                "column_edges": column_edges}
    edges, seen, node_types = [], set(), {}
    for row in (session.query(LineageEdge)
                .filter_by(project_id=project_id, from_column=None).all()):
        key = (row.from_ref, row.to_ref)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from": row.from_ref, "to": row.to_ref,
                      "from_type": row.from_type, "to_type": row.to_type,
                      "asset_id": row.to_id})
        node_types[row.from_ref] = row.from_type
        node_types[row.to_ref] = row.to_type
    column_edges = []
    for row in (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.from_column.isnot(None)).all()):
        column_edges.append({
            "from": row.from_ref, "from_column": row.from_column,
            "to": row.to_ref, "to_column": row.to_column,
            "asset_id": row.to_id})
    nodes = sorted({e["from"] for e in edges} | {e["to"] for e in edges})
    return {"focus": None, "direction": direction, "depth": depth,
            "nodes": nodes, "node_types": node_types, "edges": edges,
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
