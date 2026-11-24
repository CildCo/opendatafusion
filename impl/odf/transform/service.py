import re
import time

from sqlalchemy import text

from odf.apistudio.compiler import quote_ident
from odf.assets.service import get_asset
from odf.connectors.registry import supports
from odf.models import (Asset, AssetVersion, Datasource, JobDependency,
                        LineageEdge)
from odf.services.query import execute_query
from odf.services.sqldialect import limited
from odf.transform.content import (IDENT, compile_sql, ref_assets,
                                   validate_model)

_SCHEMA_DEFAULT = {"trino": "odf_p", "sqlite": "main", "duckdb": "main",
                   "postgres": "public"}


class ModelTestError(ValueError):
    def __init__(self, results):
        self.results = results
        failed = [r for r in results if r["status"] == "fail"]
        super().__init__("model tests failed: " + ", ".join(
            r.get("name") or r["kind"] for r in failed))


def _version(session, asset, published=True):
    version_id = (asset.published_version_id if published
                  else (asset.draft_version_id or asset.published_version_id))
    version = session.get(AssetVersion, version_id) if version_id else None
    if not version:
        raise ValueError("content not found")
    return version.content_json


def _datasource(session, content, project_id):
    ds = session.get(Datasource, content.get("datasource_id")) \
        if isinstance(content.get("datasource_id"), int) else None
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource does not belong to the project")
    if not supports(ds.kind, "query"):
        raise ValueError("datasource does not support SQL queries")
    return ds


def _schema(ds, content, project_id):
    if content.get("schema"):
        return content["schema"]
    if ds.kind == "trino":
        return "odf_p%d" % int(project_id)
    return _SCHEMA_DEFAULT.get(ds.kind, "odf_models")


def target_for(session, asset, content):
    ds = _datasource(session, content, asset.project_id)
    schema = _schema(ds, content, asset.project_id)
    if not IDENT.match(schema):
        raise ValueError("invalid schema name")
    table = asset.key
    if ds.kind == "trino":
        from odf.trino.client import client_for_datasource
        client = client_for_datasource(ds)
        catalog = getattr(client, "catalog", "") or ""
        if not IDENT.match(catalog):
            raise ValueError("trino datasource needs a catalog in the dsn")
        return ("%s.%s.%s" % (quote_ident(catalog), quote_ident(schema),
                              quote_ident(table)), ds, schema)
    return ("%s.%s" % (quote_ident(schema), quote_ident(table)), ds, schema)


def _ensure_schema(session, ds, schema, project_id):
    if ds.kind != "trino":
        return
    from odf.trino.client import client_for_datasource
    client = client_for_datasource(ds)
    catalog = getattr(client, "catalog", "") or ""
    client.execute('CREATE SCHEMA IF NOT EXISTS %s.%s'
                   % (quote_ident(catalog), quote_ident(schema)))


def _ddl(session, ds, statement):
    if ds.kind == "trino":
        from odf.trino.client import client_for_datasource
        client_for_datasource(ds).execute(statement)
        return
    from odf.services.connections import engine_for
    with engine_for(ds) as engine:
        with engine.begin() as conn:
            conn.execute(text(statement))


def _drop(session, ds, statement):
    try:
        _ddl(session, ds, statement)
    except Exception:
        pass


def _sibling(target, suffix):
    index = target.rfind('"')
    if index == -1:
        return target + suffix
    return target[:index] + suffix + target[index:]


def _swap_table(session, ds, target, shadow, table_key):
    old = _sibling(target, "__odf_old")
    _drop(session, ds, "DROP TABLE IF EXISTS %s" % old)
    new_name = quote_ident(table_key)
    if not _table_exists(session, ds, target):
        _ddl(session, ds, "ALTER TABLE %s RENAME TO %s"
             % (shadow, target if ds.kind == "trino" else new_name))
        return
    if ds.kind == "trino":
        _ddl(session, ds, "ALTER TABLE %s RENAME TO %s" % (target, old))
        _ddl(session, ds, "ALTER TABLE %s RENAME TO %s" % (shadow, target))
        _drop(session, ds, "DROP TABLE %s" % old)
        return
    if ds.kind in ("mysql", "mariadb"):
        _ddl(session, ds, "RENAME TABLE %s TO %s, %s TO %s"
             % (target, old, shadow, target))
        _drop(session, ds, "DROP TABLE %s" % old)
        return
    from odf.services.connections import engine_for
    with engine_for(ds) as engine:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS %s" % target))
            conn.execute(text("ALTER TABLE %s RENAME TO %s"
                              % (shadow, new_name)))


def _resolved(session, asset, content):
    mapping = {}
    for ref in ref_assets(session, content, asset.project_id, asset.id):
        upstream = _version(session, ref, published=True)
        qualified, _, _ = target_for(session, ref, upstream)
        mapping[ref.key] = qualified
        mapping[ref.name] = qualified
    return compile_sql(content.get("sql") or "", mapping), mapping


def compile_model(session, asset, content=None):
    if content is None:
        content = _version(session, asset, published=False)
    errs = validate_model(session, content, asset.project_id, asset.id)
    if errs:
        raise ValueError("invalid model: %s" % errs)
    sql, mapping = _resolved(session, asset, content)
    return sql, mapping


def preview_model(session, asset_id, content=None, limit=100, role=None,
                  actor=""):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "model":
        raise ValueError("model not found")
    if content is None:
        content = _version(session, asset, published=False)
    sql, mapping = compile_model(session, asset, content)
    ds = _datasource(session, content, asset.project_id)
    max_rows = max(1, min(int(limit), 10000))
    started = time.time()
    from odf.services.query_log import record as record_query
    try:
        result = execute_query(session, ds, limited(sql, ds.kind, max_rows),
                               {}, max_rows)
    except ValueError as error:
        record_query(session, asset.project_id, ds.id, actor, "model",
                     int((time.time() - started) * 1000), 0, error, sql)
        raise
    elapsed = int((time.time() - started) * 1000)
    record_query(session, asset.project_id, ds.id, actor, "model", elapsed,
                 len(result["rows"]), None, sql)
    target, _, schema = target_for(session, asset, content)
    columns = [{"name": c, "type": "unknown"}
               for c in result.get("columns") or []]
    return {"columns": columns, "rows": result["rows"],
            "row_count": result["row_count"], "ms": elapsed,
            "sql": sql, "target": target, "schema": schema}


def _table_exists(session, ds, target):
    try:
        execute_query(session, ds, limited(
            "SELECT * FROM %s" % target, ds.kind, 1), {}, 1)
        return True
    except ValueError:
        return False


def _bind_values(values):
    binds = {}
    keys = []
    for index, value in enumerate(values):
        key = "tv%d" % index
        binds[key] = value
        keys.append(":" + key)
    return keys, binds


def _test_sql(session, asset, content, test, target):
    kind = test.get("kind")
    if kind == "sql":
        return test.get("sql"), {}
    column = quote_ident(test["column"])
    if kind == "not_null":
        return ("SELECT COUNT(*) AS failures FROM %s "
                "WHERE %s IS NULL" % (target, column), {})
    if kind == "unique":
        return ("SELECT COUNT(*) - COUNT(DISTINCT %s) AS failures "
                "FROM %s" % (column, target), {})
    if kind == "accepted_values":
        keys, binds = _bind_values(test.get("values") or [])
        return ("SELECT COUNT(*) AS failures FROM %s WHERE %s NOT IN (%s)"
                % (target, column, ", ".join(keys)), binds)
    if kind == "relationships":
        wanted = test.get("to_model")
        upstream = (session.query(Asset)
                    .filter(Asset.project_id == asset.project_id,
                            Asset.type == "model",
                            Asset.published_version_id.isnot(None))
                    .filter((Asset.key == wanted) | (Asset.name == wanted))
                    .first())
        if not upstream:
            raise ValueError("relationships target is not published: %s"
                             % wanted)
        up_content = _version(session, upstream, published=True)
        up_target, _, _ = target_for(session, upstream, up_content)
        to_col = quote_ident(test["to_column"])
        return ("SELECT COUNT(*) AS failures FROM %s t LEFT JOIN %s u "
                "ON t.%s = u.%s WHERE t.%s IS NOT NULL AND u.%s IS NULL"
                % (target, up_target, column, to_col, column, to_col), {})
    raise ValueError("unsupported test kind")


def run_tests(session, asset, content, target):
    results = []
    for test in content.get("tests") or []:
        entry = {"kind": test.get("kind"), "column": test.get("column"),
                 "status": "pass", "failures": 0}
        try:
            sql, binds = _test_sql(session, asset, content, test, target)
            ds = _datasource(session, content, asset.project_id)
            result = execute_query(session, ds, sql, binds, 1)
            row = (result.get("rows") or [{}])[0]
            value = next(iter(row.values()), 0)
            count = int(value or 0)
            entry["failures"] = count
            if count > 0:
                entry["status"] = "fail"
        except Exception as error:
            entry["status"] = "fail"
            entry["error"] = str(error)[:300]
        results.append(entry)
    return results


def _create_table_sql(target, sql, partition_by=None):
    if partition_by:
        parts = ", ".join("'%s'" % column for column in partition_by)
        return ("CREATE TABLE %s WITH (format = 'PARQUET', "
                "partitioning = ARRAY[%s]) AS %s" % (target, parts, sql))
    return "CREATE TABLE %s AS %s" % (target, sql)


MERGE_KEY_CAP = 50000
MERGE_BATCH = 200


def _merge_rows(session, ds, target, sql, keys, kind):
    selected = ", ".join(quote_ident(key) for key in keys)
    count = execute_query(
        session, ds, limited("SELECT %s FROM (%s) s" % (selected, sql),
                             kind, MERGE_KEY_CAP + 1),
        {}, MERGE_KEY_CAP + 1)
    rows = count["rows"]
    if len(rows) > MERGE_KEY_CAP:
        return False
    from odf.services.connections import engine_for
    for start in range(0, len(rows), MERGE_BATCH):
        batch = rows[start:start + MERGE_BATCH]
        params, conditions = {}, []
        for i, row in enumerate(batch):
            for j, key in enumerate(keys):
                params["k%d_%d" % (i, j)] = row[key]
            conditions.append("(" + " AND ".join(
                "%s = :k%d_%d" % (quote_ident(key), i, j)
                for j, key in enumerate(keys)) + ")")
        statement = "DELETE FROM %s WHERE %s" % (
            target, " OR ".join(conditions))
        if kind == "trino":
            from odf.trino.client import render_params
            _ddl(session, ds, render_params(statement, params))
        else:
            with engine_for(ds) as engine:
                with engine.begin() as conn:
                    conn.execute(text(statement), params)
    _ddl(session, ds, "INSERT INTO %s SELECT * FROM (%s) s" % (target, sql))
    return True


def _save_result(session, job, out):
    if job is None:
        return
    payload = dict(job.payload_json or {})
    payload["last_result"] = out
    job.payload_json = payload
    session.commit()


def materialize_model(session, asset_id, job=None):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "model":
        raise ValueError("model not found")
    content = _version(session, asset, published=False)
    errs = validate_model(session, content, asset.project_id, asset.id)
    if errs:
        raise ValueError("invalid model: %s" % errs)
    sql, _ = _resolved(session, asset, content)
    ds = _datasource(session, content, asset.project_id)
    target, _, schema = target_for(session, asset, content)
    materialization = content.get("materialization")
    partition_by = content.get("partition_by") or []
    if ds.kind == "trino":
        _ensure_schema(session, ds, schema, asset.project_id)
    merged, rebuilt = False, False
    results, out = None, None
    if materialization == "view":
        _drop(session, ds, "DROP TABLE IF EXISTS %s" % target)
        _drop(session, ds, "DROP VIEW IF EXISTS %s" % target)
        _ddl(session, ds, "CREATE VIEW %s AS %s" % (target, sql))
    elif materialization == "table":
        execute_query(session, ds, limited(sql, ds.kind, 1), {}, 1)
        _drop(session, ds, "DROP VIEW IF EXISTS %s" % target)
        shadow = _sibling(target, "__odf_new")
        _drop(session, ds, "DROP TABLE IF EXISTS %s" % shadow)
        _ddl(session, ds, _create_table_sql(shadow, sql, partition_by))
        results = run_tests(session, asset, content, shadow)
        out = {"target": target, "schema": schema,
               "materialization": materialization, "merged": False,
               "rebuilt": False, "replaced": False, "tests": results}
        if any(item["status"] == "fail" for item in results):
            _drop(session, ds, "DROP TABLE IF EXISTS %s" % shadow)
            _save_result(session, job, out)
            raise ModelTestError(results)
        _swap_table(session, ds, target, shadow, asset.key)
        out["replaced"] = True
    elif materialization == "incremental":
        if not _table_exists(session, ds, target):
            _drop(session, ds, "DROP VIEW IF EXISTS %s" % target)
            _ddl(session, ds, _create_table_sql(target, sql, partition_by))
        else:
            keys = content.get("unique_key") or []
            strategy = content.get("incremental_strategy") or "append"
            if keys and strategy == "merge":
                merged = _merge_rows(session, ds, target, sql, keys,
                                     ds.kind)
                if not merged:
                    _ddl(session, ds, "DROP TABLE IF EXISTS %s" % target)
                    _ddl(session, ds,
                         _create_table_sql(target, sql, partition_by))
                    rebuilt = True
            elif keys:
                match = " AND ".join(
                    "t.%s = s.%s" % (quote_ident(k), quote_ident(k))
                    for k in keys)
                statement = (
                    "INSERT INTO %s SELECT * FROM (%s) s WHERE NOT EXISTS "
                    "(SELECT 1 FROM %s t WHERE %s)"
                    % (target, sql, target, match))
                _ddl(session, ds, statement)
            else:
                statement = "INSERT INTO %s SELECT * FROM (%s) s" % (
                    target, sql)
                _ddl(session, ds, statement)
    else:
        raise ValueError("unsupported materialization")
    if results is None:
        results = run_tests(session, asset, content, target)
        out = {"target": target, "schema": schema,
               "materialization": materialization, "merged": merged,
               "rebuilt": rebuilt, "replaced": False, "tests": results}
    _save_result(session, job, out)
    failed = [r for r in results if r["status"] == "fail"]
    if failed:
        raise ModelTestError(results)
    contract = asset.contract_json or {}
    if contract.get("schema"):
        from odf.services.contracts import check_asset
        checked = check_asset(session, asset.project_id, asset.id,
                              content=content)
        out["contract"] = checked
        if contract.get("enforce") and not checked["ok"]:
            missing = ", ".join(
                item["column"] for item in checked["issues"]
                if item["kind"] == "missing") or "schema mismatch"
            raise ValueError(
                "data contract check failed: %s" % missing)
    return out


def sync_model_graph(session, asset, content):
    refs = ref_assets(session, content, asset.project_id, asset.id)
    (session.query(JobDependency)
     .filter_by(downstream_type="model", downstream_id=asset.id).delete(
         synchronize_session=False))
    for ref in refs:
        session.add(JobDependency(project_id=asset.project_id,
                                  downstream_type="model",
                                  downstream_id=asset.id,
                                  upstream_type="model",
                                  upstream_id=ref.id))
    (session.query(LineageEdge)
     .filter(LineageEdge.project_id == asset.project_id,
             LineageEdge.to_type == "model",
             LineageEdge.to_id == str(asset.id)).delete(
                 synchronize_session=False))
    for ref in refs:
        session.add(LineageEdge(
            project_id=asset.project_id, asset_id=asset.id,
            from_type="model", from_id=str(ref.id),
            from_ref="model:%d" % ref.id,
            to_type="model", to_id=str(asset.id),
            to_ref="model:%d" % asset.id))
    session.commit()


def model_parents(session, asset, content):
    return ref_assets(session, content, asset.project_id, asset.id)


def model_target(session, asset, content=None):
    if content is None:
        content = _version(session, asset, published=False)
    target, _, schema = target_for(session, asset, content)
    return {"target": target, "schema": schema}
