import json

from odf.models import Column, Dataset, Datasource, Project
from odf.services.audit import write_audit
from odf.services.crypto import encrypt_secret

MAX_MODELS = 5000
MAX_COLUMNS = 200


def _text(value, limit=4000):
    return str(value or "").strip()[:limit]


def _name(value, fallback="item"):
    text = str(value or "").strip() or fallback
    return text[:128]


def _datasource(session, project_id, kind, name, tool):
    row = (session.query(Datasource)
           .filter_by(project_id=project_id, kind=kind, name=name).first())
    if row:
        return row
    row = Datasource(project_id=project_id, name=name, kind=kind,
                     dsn_encrypted=encrypt_secret(
                         json.dumps({"tool": tool})), auto_sync_minutes=0,
                     limit_json={"external": True, "tool": tool})
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _upsert_table(session, datasource, schema, table, description, owner,
                  columns):
    row = (session.query(Dataset)
           .filter_by(datasource_id=datasource.id,
                      schema_name=schema, table_name=table).first())
    if not row:
        row = Dataset(datasource_id=datasource.id, schema_name=schema,
                      table_name=table)
        session.add(row)
        session.flush()
    row.description = _text(description)
    row.owner = _text(owner, 64)
    existing = {col.name: col for col in
                session.query(Column).filter_by(dataset_id=row.id).all()}
    for item in columns[:MAX_COLUMNS]:
        name = _name(item.get("name"), "")
        if not name:
            continue
        col = existing.get(name)
        if not col:
            col = Column(dataset_id=row.id, name=name, data_type="")
            session.add(col)
        col.data_type = _text(item.get("type") or "unknown", 64)
        col.description = _text(item.get("description"))
    return row


def import_external(session, project_id, source, text, actor):
    if not session.get(Project, project_id):
        raise ValueError("project not found")
    if source not in ("dbt", "bi"):
        raise ValueError("source must be dbt or bi")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("metadata text is required")
    if len(text.encode("utf-8")) > 10 * 1024 * 1024:
        raise ValueError("metadata is too large")
    try:
        payload = json.loads(text)
    except ValueError:
        raise ValueError("metadata must be valid JSON")
    if not isinstance(payload, dict):
        raise ValueError("metadata must be an object")
    tables = 0
    columns = 0

    if source == "dbt":
        nodes = payload.get("nodes")
        if not isinstance(nodes, dict):
            raise ValueError("dbt manifest is missing nodes")
        project_name = _name((payload.get("metadata") or {}).get(
            "project_name") or "dbt", "dbt")
        datasource = _datasource(session, project_id, "dbt",
                                 "dbt %s" % project_name, "dbt")
        selected = [node for node in nodes.values()
                    if isinstance(node, dict)
                    and node.get("resource_type") in (
                        "model", "source", "seed", "snapshot")]
        if len(selected) > MAX_MODELS:
            raise ValueError("too many dbt models (max %d)" % MAX_MODELS)
        for node in selected:
            schema = _name(node.get("schema") or node.get("package_name")
                           or "dbt")
            table = _name(node.get("alias") or node.get("name"), "")
            if not table:
                continue
            raw_columns = node.get("columns") or {}
            cols = []
            if isinstance(raw_columns, dict):
                for name, meta in raw_columns.items():
                    meta = meta if isinstance(meta, dict) else {}
                    cols.append({"name": name,
                                 "type": meta.get("data_type") or "unknown",
                                 "description": meta.get("description")})
            _upsert_table(session, datasource, schema, table,
                          node.get("description"), "", cols)
            tables += 1
            columns += len(cols)
    else:
        tool = _name(payload.get("tool") or "bi", "bi")
        reports = payload.get("reports")
        if not isinstance(reports, list):
            raise ValueError("BI metadata is missing reports")
        if len(reports) > MAX_MODELS:
            raise ValueError("too many reports (max %d)" % MAX_MODELS)
        datasource = _datasource(session, project_id, "bi",
                                 "bi %s" % tool, tool)
        for report in reports:
            if not isinstance(report, dict):
                continue
            schema = _name(report.get("schema") or tool)
            table = _name(report.get("name"), "")
            if not table:
                continue
            raw_columns = report.get("columns") or []
            cols = [item for item in raw_columns if isinstance(item, dict)]
            _upsert_table(session, datasource, schema, table,
                          report.get("description"), report.get("owner"),
                          cols)
            tables += 1
            columns += len(cols)

    session.commit()
    write_audit(session, actor, "import_external_metadata",
                str(datasource.id), {"source": source, "tables": tables,
                                     "columns": columns})
    return {"source": source, "datasource_id": datasource.id,
            "tables": tables, "columns": columns}
