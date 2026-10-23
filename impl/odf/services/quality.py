import re
from datetime import date, datetime, timezone

from sqlalchemy import (MetaData, Table, create_engine, false, func, or_,
                        select)

from odf.apistudio.catalog import table_column_info
from odf.models import Dataset, Datasource, QualityResult, QualityRule
from odf.services.datasource import connect_args_for, get_dsn


def _dataset_project(session, dataset_id: int):
    return (session.query(Datasource.project_id)
            .join(Dataset, Dataset.datasource_id == Datasource.id)
            .filter(Dataset.id == dataset_id).scalar())


def create_rule(session, project_id: int, dataset_id: int, name: str,
                kind: str, column_name: str | None = None,
                config: dict | None = None) -> QualityRule:
    if _dataset_project(session, dataset_id) != project_id:
        raise ValueError("dataset not found")
    rule = QualityRule(project_id=project_id, dataset_id=dataset_id,
                       name=name, kind=kind, column_name=column_name,
                       config_json=config or {}, enabled=True)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def list_rules(session, project_id: int):
    return (session.query(QualityRule).filter_by(project_id=project_id)
            .order_by(QualityRule.id).all())


def _simple_runner(datasource):
    from odf import clickhouse, filesource
    return filesource if datasource.kind == "file" else clickhouse


def _as_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day,
                        tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(
                tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _freshness(value, max_age_hours):
    parsed = _as_datetime(value)
    if parsed is None:
        return False, {"error": "no timestamp value",
                       "max_age_hours": max_age_hours}
    age = (datetime.now(timezone.utc) - parsed).total_seconds() / 3600
    return age <= max_age_hours, {
        "latest": parsed.isoformat(), "age_hours": round(age, 2),
        "max_age_hours": max_age_hours}


def _schema_check(actual, expected, allow_extra=False):
    expected = [str(x) for x in expected or []]
    missing = [x for x in expected if x not in actual]
    extra = [x for x in actual if x not in expected]
    ok = not missing and (allow_extra or not extra)
    return ok, {"missing": missing, "extra": extra,
                "expected": expected}


def _run_simple(session, datasource, ds, rule):
    from odf.apistudio.compiler import quote_ident
    runner = _simple_runner(datasource)
    schema = "file" if datasource.kind == "file" else ds.schema_name
    table = "%s.%s" % (quote_ident(schema), quote_ident(ds.table_name))
    col = quote_ident(rule.column_name) if rule.column_name else None
    cfg = rule.config_json or {}
    if rule.kind == "not_null":
        rows = runner.execute(
            datasource, "SELECT count(*) AS n FROM %s WHERE %s IS NULL"
            % (table, col), {}, 1)["rows"]
        bad = rows[0]["n"]
        ok, detail = bad == 0, {"nulls": bad}
    elif rule.kind == "unique":
        rows = runner.execute(
            datasource, "SELECT count(*) AS total, count(DISTINCT %s) "
            "AS distinct_rows FROM %s" % (col, table), {}, 1)["rows"]
        total, distinct = rows[0]["total"], rows[0]["distinct_rows"]
        bad = total - distinct
        ok, detail = bad == 0, {"duplicates": bad, "total": total}
    elif rule.kind == "row_count":
        rows = runner.execute(
            datasource, "SELECT count(*) AS n FROM %s" % table, {}, 1)["rows"]
        n = rows[0]["n"]
        lo, hi = cfg.get("min"), cfg.get("max")
        ok = (lo is None or n >= lo) and (hi is None or n <= hi)
        detail = {"rows": n, "min": lo, "max": hi}
    elif rule.kind == "freshness":
        rows = runner.execute(
            datasource, "SELECT max(%s) AS value FROM %s" % (col, table),
            {}, 1)["rows"]
        ok, detail = _freshness(rows[0]["value"], cfg.get("max_age_hours", 24))
    elif rule.kind == "regex":
        pattern = cfg.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return False, {"error": "pattern is required"}
        values = runner.execute(
            datasource, "SELECT %s AS value FROM %s" % (col, table),
            {}, 100000)["rows"]
        compiled = re.compile(pattern)
        invalid = 0
        checked = 0
        for row in values:
            value = row["value"]
            if value is None:
                if not cfg.get("allow_null", True):
                    invalid += 1
                continue
            checked += 1
            if not compiled.search(str(value)):
                invalid += 1
        ok, detail = invalid == 0, {"invalid": invalid, "checked": checked}
    elif rule.kind == "accepted_values":
        accepted = cfg.get("values")
        if not isinstance(accepted, list) or not accepted:
            return False, {"error": "values are required"}
        values = runner.execute(
            datasource, "SELECT %s AS value FROM %s" % (col, table),
            {}, 100000)["rows"]
        bad = 0
        for row in values:
            value = row["value"]
            if value is None:
                bad += 0 if cfg.get("allow_null", True) else 1
            elif value not in accepted:
                bad += 1
        ok, detail = bad == 0, {"invalid": bad, "checked": len(values)}
    elif rule.kind == "schema":
        actual = [c["name"] for c in table_column_info(
            session, datasource, ds.table_name)]
        ok, detail = _schema_check(actual, cfg.get("expected"),
                                   cfg.get("allow_extra", False))
    elif rule.kind == "range":
        conds, params = [], {}
        if cfg.get("min") is not None:
            conds.append("%s < :rmin" % col)
            params["rmin"] = cfg["min"]
        if cfg.get("max") is not None:
            conds.append("%s > :rmax" % col)
            params["rmax"] = cfg["max"]
        where = " OR ".join(conds) if conds else "1 = 0"
        rows = runner.execute(
            datasource, "SELECT count(*) AS n FROM %s WHERE %s"
            % (table, where), params, 1)["rows"]
        bad = rows[0]["n"]
        ok, detail = bad == 0, {"out_of_range": bad}
    else:
        ok, detail = False, {"error": "unsupported kind"}
    return ok, detail


def run_rule(session, rule_id: int, project_id: int | None = None) -> QualityResult:
    rule = session.get(QualityRule, rule_id)
    if not rule or (project_id is not None and rule.project_id != project_id):
        raise ValueError("rule not found")
    ds = session.get(Dataset, rule.dataset_id)
    if not ds:
        raise ValueError("rule not found")
    datasource = session.get(Datasource, ds.datasource_id)
    if not datasource:
        raise ValueError("rule not found")
    if datasource.kind in ("file", "clickhouse"):
        ok, detail = _run_simple(session, datasource, ds, rule)
        result = QualityResult(rule_id=rule.id,
                               status="pass" if ok else "fail",
                               detail_json=detail)
        session.add(result)
        session.commit()
        session.refresh(result)
        return result
    dsn = get_dsn(datasource)
    engine = create_engine(dsn, connect_args=connect_args_for(
        datasource.kind, dsn))
    schema = None if ds.schema_name in ("main", None) else ds.schema_name
    t = Table(ds.table_name, MetaData(), schema=schema, autoload_with=engine)

    with engine.connect() as c:
        if rule.kind == "not_null":
            bad = c.execute(select(func.count()).select_from(t).where(
                t.c[rule.column_name].is_(None))).scalar()
            ok, detail = bad == 0, {"nulls": bad}
        elif rule.kind == "unique":
            total = c.execute(select(func.count()).select_from(t)).scalar()
            distinct = c.execute(select(
                func.count(t.c[rule.column_name].distinct())).select_from(t)).scalar()
            bad = total - distinct
            ok, detail = bad == 0, {"duplicates": bad, "total": total}
        elif rule.kind == "row_count":
            n = c.execute(select(func.count()).select_from(t)).scalar()
            cfg = rule.config_json or {}
            lo, hi = cfg.get("min"), cfg.get("max")
            ok = (lo is None or n >= lo) and (hi is None or n <= hi)
            detail = {"rows": n, "min": lo, "max": hi}
        elif rule.kind == "freshness":
            cfg = rule.config_json or {}
            value = c.execute(select(func.max(t.c[rule.column_name]))).scalar()
            ok, detail = _freshness(value, cfg.get("max_age_hours", 24))
        elif rule.kind == "regex":
            cfg = rule.config_json or {}
            pattern = cfg.get("pattern")
            if not isinstance(pattern, str) or not pattern:
                ok, detail = False, {"error": "pattern is required"}
            else:
                compiled = re.compile(pattern)
                values = c.execute(
                    select(t.c[rule.column_name])).fetchmany(100000)
                invalid = checked = 0
                for (value,) in values:
                    if value is None:
                        if not cfg.get("allow_null", True):
                            invalid += 1
                        continue
                    checked += 1
                    if not compiled.search(str(value)):
                        invalid += 1
                ok, detail = invalid == 0, {"invalid": invalid,
                                            "checked": checked}
        elif rule.kind == "accepted_values":
            cfg = rule.config_json or {}
            accepted = cfg.get("values")
            if not isinstance(accepted, list) or not accepted:
                ok, detail = False, {"error": "values are required"}
            else:
                values = c.execute(
                    select(t.c[rule.column_name])).fetchmany(100000)
                bad = 0
                for (value,) in values:
                    if value is None:
                        bad += 0 if cfg.get("allow_null", True) else 1
                    elif value not in accepted:
                        bad += 1
                ok, detail = bad == 0, {"invalid": bad,
                                        "checked": len(values)}
        elif rule.kind == "schema":
            cfg = rule.config_json or {}
            actual_columns = [x["name"] for x in table_column_info(
                session, datasource, ds.table_name)]
            ok, detail = _schema_check(actual_columns,
                                       cfg.get("expected"),
                                       cfg.get("allow_extra", False))
        elif rule.kind == "range":
            col = t.c[rule.column_name]
            cfg = rule.config_json or {}
            conds = []
            if cfg.get("min") is not None:
                conds.append(col < cfg["min"])
            if cfg.get("max") is not None:
                conds.append(col > cfg["max"])
            where = or_(*conds) if conds else false()
            bad = c.execute(select(func.count()).select_from(t).where(where)).scalar()
            ok, detail = bad == 0, {"out_of_range": bad}
        else:
            ok, detail = False, {"error": "unsupported kind"}

    result = QualityResult(rule_id=rule.id,
                           status="pass" if ok else "fail",
                           detail_json=detail)
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def list_results(session, rule_id: int, project_id: int | None = None):
    rule = session.get(QualityRule, rule_id)
    if not rule or (project_id is not None and rule.project_id != project_id):
        raise ValueError("rule not found")
    return (session.query(QualityResult).filter_by(rule_id=rule_id)
            .order_by(QualityResult.id.desc()).limit(100).all())
