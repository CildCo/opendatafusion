import sqlglot
from sqlglot import exp

from odf.models import ColumnPolicy
from odf.transform.content import ref_assets
from odf.transform.service import _datasource, _schema, target_for


def _parent_columns(session, parent):
    from odf.models import AssetVersion
    version_id = parent.published_version_id or parent.draft_version_id
    version = session.get(AssetVersion, version_id) if version_id else None
    content = (version.content_json or {}) if version else {}
    return [column.get("name") for column in content.get("columns") or []
            if isinstance(column, dict)], content


def _source_table(session, asset, content):
    sql = content.get("sql") or ""
    if "{{" in sql:
        return None, None
    try:
        expression = sqlglot.parse_one(sql)
    except Exception:
        return None, None
    tables = [table for table in expression.find_all(exp.Table)
              if table.name]
    if len(tables) != 1:
        return None, None
    table = tables[0]
    schema = table.db or content.get("schema") or ""
    return (schema, table.name)


def _policy(session, datasource_id, schema, table, column):
    candidates = [schema or ""]
    if "" not in candidates:
        candidates.append("")
    for name in candidates:
        row = (session.query(ColumnPolicy)
               .filter_by(datasource_id=datasource_id, schema_name=name,
                          table_name=table, column_name=column).first())
        if row:
            return row
    return None


def _upsert(session, project_id, datasource_id, schema, table, column,
            source_policy):
    row = (session.query(ColumnPolicy)
           .filter_by(datasource_id=datasource_id, schema_name=schema or "",
                      table_name=table, column_name=column).first())
    if row and row.source != "lineage":
        return False
    if not row:
        row = ColumnPolicy(project_id=project_id,
                           datasource_id=datasource_id,
                           schema_name=schema or "", table_name=table,
                           column_name=column, created_by="system:lineage")
        session.add(row)
    row.classification = source_policy.classification
    row.mask_type = source_policy.mask_type
    row.exempt_roles_json = list(source_policy.exempt_roles_json or [])
    row.source = "lineage"
    return True


def propagate_model_policies(session, asset, content):
    parents = ref_assets(session, content, asset.project_id, asset.id)
    by_name = {}
    for parent in parents:
        by_name[parent.key] = parent
        by_name[parent.name] = parent
    parent_columns = {}
    for parent in parents:
        names, parent_content = _parent_columns(session, parent)
        parent_columns[parent.id] = set(names)
    raw_schema, raw_table = _source_table(session, asset, content)
    try:
        datasource = _datasource(session, content, asset.project_id)
    except ValueError:
        return 0
    target_schema = _schema(datasource, content, asset.project_id)
    applied = set()
    for column in content.get("columns") or []:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        source = str(column.get("source") or "").strip()
        if not name or not source:
            continue
        parent = None
        source_column = source
        if "." in source:
            prefix, source_column = source.split(".", 1)
            parent = by_name.get(prefix)
        else:
            matched = [item for item in parents
                       if source_column in parent_columns[item.id]]
            if len(matched) == 1:
                parent = matched[0]
        source_policy = None
        if parent is not None:
            parent_content = None
            version_id = (parent.published_version_id
                          or parent.draft_version_id)
            from odf.models import AssetVersion
            version = session.get(AssetVersion, version_id) \
                if version_id else None
            parent_content = (version.content_json or {}) if version else {}
            _, parent_ds, parent_schema = target_for(
                session, parent, parent_content)
            source_policy = _policy(session, parent_ds.id, parent_schema,
                                    parent.key, source_column)
        elif raw_table:
            source_policy = _policy(session, datasource.id, raw_schema,
                                    raw_table, source_column)
        if not source_policy:
            continue
        _upsert(session, asset.project_id, datasource.id, target_schema,
                asset.key, name, source_policy)
        applied.add(name)
    stale = (session.query(ColumnPolicy)
             .filter_by(datasource_id=datasource.id,
                        schema_name=target_schema or "",
                        table_name=asset.key, source="lineage").all())
    for row in stale:
        if row.column_name not in applied:
            session.delete(row)
    return len(applied)
