from sqlalchemy import func

from odf.models import (Column, Dataset, DatasetTag, Datasource, Flow,
                        FlowVersion, LineageEdge, Tag)


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
    row = DatasetTag(dataset_id=dataset_id, tag_id=tag_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_datasets(session, project_id: int | None = None):
    q = (session.query(Dataset)
         .join(Datasource, Dataset.datasource_id == Datasource.id))
    if project_id is not None:
        q = q.filter(Datasource.project_id == project_id)
    return [{"id": d.id, "datasource_id": d.datasource_id,
             "schema": d.schema_name, "table": d.table_name}
            for d in q.order_by(Dataset.id).all()]


def dataset_detail(session, dataset_id: int, project_id: int | None = None):
    d = session.get(Dataset, dataset_id)
    if not d:
        return None
    ds = session.get(Datasource, d.datasource_id)
    if project_id is not None and (not ds or ds.project_id != project_id):
        return None
    cols = (session.query(Column).filter_by(dataset_id=dataset_id)
            .order_by(Column.id).all())
    tags = (session.query(Tag)
            .join(DatasetTag, DatasetTag.tag_id == Tag.id)
            .filter(DatasetTag.dataset_id == dataset_id).all())
    return {"id": d.id, "datasource_id": d.datasource_id,
            "schema": d.schema_name, "table": d.table_name,
            "columns": [{"name": c.name, "type": c.data_type} for c in cols],
            "tags": [t.name for t in tags]}


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


def _label(datasource_id, table: str | None) -> str | None:
    if datasource_id is None or not table:
        return None
    return "%s:%s" % (datasource_id, table)


def lineage(session, project_id: int):
    edges, seen = [], set()
    for f in session.query(Flow).filter_by(project_id=project_id).all():
        v = (session.query(FlowVersion)
             .filter_by(flow_id=f.id, version=f.current_version).first())
        if not v:
            continue
        dag = v.dag_json or {}
        src = _label(dag.get("source_ds_id"), dag.get("source_table"))
        dst = _label(dag.get("sink_ds_id"), dag.get("sink_table"))
        if src and dst:
            key = (src, dst)
            if key not in seen:
                seen.add(key)
                edges.append({"from": src, "to": dst,
                              "flow_id": f.id, "flow": f.name})
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
