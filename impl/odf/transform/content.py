import re

from odf.apistudio.sqlguard import ensure_read_only

REF = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
MATERIALIZATIONS = ("view", "table", "incremental")
INCREMENTAL_STRATEGIES = ("append", "merge", "partition")
LAYERS = ("raw", "staging", "intermediate", "mart")
TEST_KINDS = ("not_null", "unique", "accepted_values", "relationships", "sql")


def empty_model():
    return {"datasource_id": None, "sql": "",
            "materialization": "table", "schema": "",
            "unique_key": [], "layer": "staging", "description": "",
            "tests": [], "columns": [], "partition_by": [],
            "incremental_strategy": "append"}


def refs(sql):
    seen = []
    for match in REF.finditer(sql or ""):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _err(field, message):
    return {"field": field, "message": message}


def _refs(session, content, project_id, asset_id=None):
    from odf.models import Asset
    out = []
    for name in refs(content.get("sql")):
        row = (session.query(Asset)
               .filter(Asset.project_id == project_id,
                       Asset.type == "model")
               .filter((Asset.key == name) | (Asset.name == name))
               .first())
        if not row:
            raise ValueError("unknown model reference: %s" % name)
        if asset_id is not None and row.id == asset_id:
            raise ValueError("a model cannot reference itself")
        if not row.published_version_id:
            raise ValueError("referenced model is not published: %s" % name)
        out.append(row)
    return out


def ref_assets(session, content, project_id, asset_id=None):
    return _refs(session, content, project_id, asset_id)


def _cycle(session, asset_id, content, project_id):
    from odf.models import Asset
    if asset_id is None:
        return False
    edges = {}
    seen = set()
    stack = [asset_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        row = session.get(Asset, current)
        if not row:
            continue
        version_id = row.published_version_id or row.draft_version_id
        if not version_id:
            continue
        from odf.models import AssetVersion
        version = session.get(AssetVersion, version_id)
        if not version:
            continue
        for ref in _refs(session, version.content_json, project_id,
                         current):
            if ref.id == asset_id:
                return True
            stack.append(ref.id)
    return False


def validate_model(session, content, project_id, asset_id=None):
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    errs = []
    from odf.models import Datasource
    from odf.connectors.registry import supports
    ds = session.get(Datasource, content.get("datasource_id")) \
        if isinstance(content.get("datasource_id"), int) else None
    if not ds or ds.project_id != project_id:
        errs.append(_err("datasource_id",
                         "datasource does not belong to the project"))
    elif not supports(ds.kind, "query"):
        errs.append(_err("datasource_id",
                         "datasource does not support SQL queries"))
    sql = content.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        errs.append(_err("sql", "SQL is required"))
    else:
        try:
            ensure_read_only(REF.sub('"__model_ref__"', sql))
        except Exception:
            errs.append(_err("sql", "SQL must be a single read-only query"))
        if len(sql) > 200000:
            errs.append(_err("sql", "SQL is too large"))
    materialization = content.get("materialization")
    if materialization not in MATERIALIZATIONS:
        errs.append(_err("materialization",
                         "materialization must be view, table or incremental"))
    layer = content.get("layer")
    if layer not in LAYERS:
        errs.append(_err("layer",
                         "layer must be raw, staging, intermediate or mart"))
    schema = content.get("schema") or ""
    if schema and not IDENT.match(schema):
        errs.append(_err("schema", "invalid schema name"))
    if ds and ds.kind in ("postgres", "mysql", "mariadb", "clickhouse") \
            and not schema:
        errs.append(_err("schema",
                         "schema is required for this datasource"))
    key = content.get("unique_key") or []
    if not isinstance(key, list) or \
            any(not isinstance(x, str) or not IDENT.match(x) for x in key):
        errs.append(_err("unique_key", "unique_key must be column names"))
    elif len(key) > 8:
        errs.append(_err("unique_key", "at most 8 unique columns"))
    strategy = content.get("incremental_strategy") or "append"
    if strategy not in INCREMENTAL_STRATEGIES:
        errs.append(_err("incremental_strategy",
                         "incremental_strategy must be append or merge"))
    elif strategy == "merge" and materialization != "incremental":
        errs.append(_err("incremental_strategy",
                         "merge is only available for incremental models"))
    elif strategy == "merge" and isinstance(key, list) and not key:
        errs.append(_err("incremental_strategy",
                         "merge requires at least one unique_key column"))
    elif strategy == "partition" and materialization != "incremental":
        errs.append(_err("incremental_strategy",
                         "partition replace needs an incremental model"))
    partition = content.get("partition_by") or []
    if not isinstance(partition, list) or any(
            not isinstance(x, str) or not IDENT.match(x) for x in partition):
        errs.append(_err("partition_by",
                         "partition columns must be identifiers"))
    elif len(partition) > 4:
        errs.append(_err("partition_by", "at most 4 partition columns"))
    elif len(set(partition)) != len(partition):
        errs.append(_err("partition_by", "duplicate partition columns"))
    elif partition and materialization == "view":
        errs.append(_err("partition_by",
                         "views cannot be partitioned"))
    elif partition and ds and ds.kind != "trino":
        errs.append(_err("partition_by",
                         "partitioning requires a Trino datasource"))
    elif strategy == "partition" and isinstance(partition, list)             and not partition:
        errs.append(_err("incremental_strategy",
                         "partition replace requires partition columns"))
    columns = content.get("columns") or []
    if not isinstance(columns, list):
        errs.append(_err("columns", "columns must be an array"))
    else:
        if len(columns) > 500:
            errs.append(_err("columns", "at most 500 columns"))
        seen_columns = set()
        for column in columns:
            if not isinstance(column, dict) or \
                    not isinstance(column.get("name"), str) or \
                    not IDENT.match(column["name"]):
                errs.append(_err("columns",
                                 "column definitions need a valid name"))
                continue
            name = column["name"]
            if name in seen_columns:
                errs.append(_err("columns", "duplicate column: %s" % name))
            seen_columns.add(name)
            source = column.get("source") or ""
            if source and (not isinstance(source, str) or not re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?",
                    source)):
                errs.append(_err("columns",
                                 "source must be column or ref.column"))
            data_type = column.get("type") or ""
            if not isinstance(data_type, str) or len(data_type) > 64:
                errs.append(_err("columns", "invalid column type"))
            description = column.get("description") or ""
            if not isinstance(description, str) or len(description) > 200:
                errs.append(_err("columns", "column description is too long"))
    tests = content.get("tests") or []
    if not isinstance(tests, list):
        errs.append(_err("tests", "tests must be an array"))
    else:
        for test in tests:
            if not isinstance(test, dict):
                errs.append(_err("tests", "test must be an object"))
                continue
            kind = test.get("kind")
            if kind not in TEST_KINDS:
                errs.append(_err("tests", "unsupported test kind"))
                continue
            if kind == "sql":
                if not isinstance(test.get("sql"), str) or \
                        not test["sql"].strip():
                    errs.append(_err("tests", "SQL test needs a query"))
                else:
                    try:
                        ensure_read_only(test["sql"])
                    except Exception:
                        errs.append(_err("tests",
                                         "SQL test must be read-only"))
                continue
            column = test.get("column")
            if not isinstance(column, str) or not column:
                errs.append(_err("tests", "test needs a column"))
            if kind == "accepted_values":
                values = test.get("values")
                if not isinstance(values, list) or not values:
                    errs.append(_err("tests",
                                     "accepted_values needs a value list"))
            if kind == "relationships":
                if not isinstance(test.get("to_model"), str) or \
                        not test["to_model"]:
                    errs.append(_err("tests",
                                     "relationships needs to_model"))
                if not isinstance(test.get("to_column"), str) or \
                        not test["to_column"]:
                    errs.append(_err("tests",
                                     "relationships needs to_column"))
    if isinstance(sql, str) and sql.strip():
        try:
            _refs(session, content, project_id, asset_id)
            if _cycle(session, asset_id, content, project_id):
                errs.append(_err("sql", "model references form a cycle"))
        except ValueError:
            errs.append(_err("sql", "could not resolve model references"))
    return errs


def compile_sql(sql, resolved):
    def repl(match):
        name = match.group(1).strip()
        value = resolved.get(name)
        if not value:
            raise ValueError("unresolved model reference: %s" % name)
        return value
    return REF.sub(repl, sql or "")
