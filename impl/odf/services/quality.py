import re
from datetime import date, datetime, timezone

from sqlalchemy import (MetaData, Table, create_engine, false, func, or_,
                        select, text)

from odf.apistudio.catalog import table_column_info
from odf.models import Dataset, Datasource, QualityResult, QualityRule
from odf.services.datasource import connect_args_for, get_dsn


def datasource_database(datasource):
    from odf.connectors import hive
    return hive.options(get_dsn(datasource))["database"]


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


class _TrinoRunner:
    """Trino has no SQLAlchemy dialect; run the same generated SQL through the
    REST client instead."""

    def execute(self, datasource, sql, params, limit):
        from odf.services.query import execute_query
        return execute_query(None, datasource, sql, params, limit)


def _simple_runner(datasource):
    from odf import clickhouse, filesource
    if datasource.kind == "trino":
        return _TrinoRunner()
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


def _custom_sql_result(n, cfg):
    expect = cfg.get("expect") or "zero"
    value = cfg.get("value")
    if expect == "nonzero":
        ok = n > 0
    elif expect == "max_rows":
        ok = value is not None and n <= int(value)
    elif expect == "min_rows":
        ok = value is not None and n >= int(value)
    else:
        ok = n == 0
    return ok, {"rows": n, "expect": expect, "value": value}


def _anomaly_result(session, rule, n, cfg):
    try:
        window = max(3, min(int(cfg.get("window") or 10), 100))
        threshold = max(1.0, min(float(cfg.get("deviation_pct") or 30), 500))
    except (TypeError, ValueError):
        window, threshold = 10, 30.0
    rows = (session.query(QualityResult)
            .filter_by(rule_id=rule.id)
            .order_by(QualityResult.id.desc()).limit(window).all())
    history = [r.detail_json.get("rows") for r in rows
               if isinstance(r.detail_json, dict)
               and isinstance(r.detail_json.get("rows"), (int, float))]
    if len(history) < 3:
        return True, {"rows": n, "baseline": "building",
                      "samples": len(history), "threshold_pct": threshold}
    mean = sum(history) / len(history)
    deviation = abs(n - mean) / mean * 100 if mean else (
        0 if n == 0 else 100)
    ok = deviation <= threshold
    return ok, {"rows": n, "mean": round(mean, 2),
                "deviation_pct": round(deviation, 2),
                "threshold_pct": threshold, "samples": len(history)}


def _drift_stats(rows, nulls, values):
    numeric = []
    for value in values:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    total = int(rows or 0)
    null_count = int(nulls or 0)
    mean = sum(numeric) / len(numeric) if numeric else None
    variance = (sum((x - mean) ** 2 for x in numeric) / len(numeric)
                if numeric and mean is not None else None)
    return {"rows": total, "null_pct": round(
        null_count * 100.0 / total, 4) if total else 0.0,
        "mean": round(mean, 6) if mean is not None else None,
        "stddev": round(variance ** 0.5, 6)
        if variance is not None else None,
        "numeric": len(numeric)}


def _drift_result(session, rule, stats, cfg):
    try:
        window = max(3, min(int(cfg.get("window") or 10), 50))
        mean_threshold = max(1.0, min(float(
            cfg.get("mean_deviation_pct") or 30), 500))
        null_threshold = max(0.0, min(float(
            cfg.get("null_delta_pct") or 10), 100))
    except (TypeError, ValueError):
        window, mean_threshold, null_threshold = 10, 30.0, 10.0
    rows = (session.query(QualityResult)
            .filter_by(rule_id=rule.id)
            .order_by(QualityResult.id.desc()).limit(window).all())
    history = [r.detail_json.get("drift") for r in rows
               if isinstance(r.detail_json, dict)
               and isinstance(r.detail_json.get("drift"), dict)]
    history = [item for item in history
               if isinstance(item.get("null_pct"), (int, float))]
    if len(history) < 3:
        return True, {"drift": stats, "baseline": "building",
                      "samples": len(history),
                      "mean_threshold_pct": mean_threshold,
                      "null_threshold_pct": null_threshold}
    means = [item.get("mean") for item in history
             if isinstance(item.get("mean"), (int, float))]
    nulls = [float(item.get("null_pct") or 0) for item in history]
    mean_base = sum(means) / len(means) if means else None
    null_base = sum(nulls) / len(nulls)
    mean_dev = None
    if stats.get("mean") is not None and mean_base not in (None, 0):
        mean_dev = abs(stats["mean"] - mean_base) / abs(mean_base) * 100
    null_delta = abs(stats["null_pct"] - null_base)
    ok = ((mean_dev is None or mean_dev <= mean_threshold)
          and null_delta <= null_threshold)
    return ok, {"drift": stats, "mean_baseline": round(mean_base, 6)
                if mean_base is not None else None,
                "null_baseline_pct": round(null_base, 4),
                "mean_deviation_pct": round(mean_dev, 4)
                if mean_dev is not None else None,
                "null_delta_pct": round(null_delta, 4),
                "mean_threshold_pct": mean_threshold,
                "null_threshold_pct": null_threshold,
                "samples": len(history)}


def _run_simple(session, datasource, ds, rule, runner=None, schema=None):
    from odf.apistudio.compiler import quote_ident
    runner = runner or _simple_runner(datasource)
    schema = schema or ("file" if datasource.kind == "file"
                        else ds.schema_name)
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
    elif rule.kind == "custom_sql":
        from odf.apistudio.sqlguard import ensure_read_only
        sql = (cfg.get("sql") or "").strip().rstrip(";")
        if not sql:
            return False, {"error": "sql is required"}
        try:
            ensure_read_only(sql)
        except Exception as exc:
            return False, {"error": str(exc)}
        rows = runner.execute(
            datasource, "SELECT count(*) AS n FROM (%s) AS odf_q" % sql,
            {}, 1)["rows"]
        ok, detail = _custom_sql_result(rows[0]["n"], cfg)
    elif rule.kind == "row_count_anomaly":
        rows = runner.execute(
            datasource, "SELECT count(*) AS n FROM %s" % table, {}, 1)["rows"]
        ok, detail = _anomaly_result(session, rule, rows[0]["n"], cfg)
    elif rule.kind == "distribution_drift":
        if not col:
            return False, {"error": "drift requires a column"}
        rows = runner.execute(
            datasource,
            "SELECT count(*) AS n, sum(CASE WHEN %s IS NULL THEN 1 "
            "ELSE 0 END) AS nulls FROM %s" % (col, table), {}, 1)["rows"]
        values = runner.execute(
            datasource, "SELECT %s AS v FROM %s WHERE %s IS NOT NULL "
            "LIMIT 10000" % (col, table, col), {}, 10000)["rows"]
        stats = _drift_stats(rows[0]["n"], rows[0].get("nulls"),
                             [row.get("v") for row in values])
        ok, detail = _drift_result(session, rule, stats, cfg)
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
    from odf.connectors.registry import supports
    if not supports(datasource.kind, "query"):
        raise ValueError("%s is a pipeline connector; quality rules are not "
                         "supported" % datasource.kind)
    if datasource.kind == "dm":
        from odf.connectors import dm

        class _DmRunner:
            def __init__(self, dsn):
                self.dsn = dsn

            def execute(self, _datasource, sql, params, limit):
                return dm.query(self.dsn, sql, limit)

        ok, detail = _run_simple(
            session, datasource, ds, rule,
            runner=_DmRunner(get_dsn(datasource)),
            schema=dm.options(get_dsn(datasource))["schema"])
        result = QualityResult(rule_id=rule.id,
                               status="pass" if ok else "fail",
                               detail_json=detail)
        session.add(result)
        session.commit()
        session.refresh(result)
        return result
    if datasource.kind == "hive":
        from odf.connectors import hive

        class _HiveRunner:
            def __init__(self, dsn):
                self.dsn = dsn

            def execute(self, _datasource, sql, params, limit):
                return hive.query(self.dsn, sql, limit)

        ok, detail = _run_simple(
            session, datasource, ds, rule,
            runner=_HiveRunner(get_dsn(datasource)),
            schema=datasource_database(datasource))
        result = QualityResult(rule_id=rule.id,
                               status="pass" if ok else "fail",
                               detail_json=detail)
        session.add(result)
        session.commit()
        session.refresh(result)
        return result
    if datasource.kind == "s3":
        import shutil
        from odf import filesource
        from odf.connectors import s3

        class _Runner:
            def __init__(self, path):
                self.ds = s3.as_file_ds(path)

            def execute(self, _datasource, sql, params, limit):
                return filesource.execute(self.ds, sql, params, limit)

        path, directory = s3.temp_file(get_dsn(datasource))
        try:
            ok, detail = _run_simple(session, datasource, ds, rule,
                                     runner=_Runner(path), schema="file")
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        result = QualityResult(rule_id=rule.id,
                               status="pass" if ok else "fail",
                               detail_json=detail)
        session.add(result)
        session.commit()
        session.refresh(result)
        return result
    if datasource.kind in ("file", "clickhouse", "trino"):
        ok, detail = _run_simple(session, datasource, ds, rule)
        result = QualityResult(rule_id=rule.id,
                               status="pass" if ok else "fail",
                               detail_json=detail)
        session.add(result)
        session.commit()
        session.refresh(result)
        return result
    dsn = get_dsn(datasource)
    from odf.services.connections import engine_for
    with engine_for(datasource) as engine:
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
            elif rule.kind == "custom_sql":
                from odf.apistudio.sqlguard import ensure_read_only
                cfg = rule.config_json or {}
                sql = (cfg.get("sql") or "").strip().rstrip(";")
                if not sql:
                    ok, detail = False, {"error": "sql is required"}
                else:
                    try:
                        ensure_read_only(sql)
                        n = c.execute(text(
                            "SELECT count(*) FROM (%s) AS odf_q"
                            % sql)).scalar()
                        ok, detail = _custom_sql_result(n, cfg)
                    except Exception as exc:
                        ok, detail = False, {"error": str(exc)[:300]}
            elif rule.kind == "row_count_anomaly":
                n = c.execute(select(func.count()).select_from(t)).scalar()
                ok, detail = _anomaly_result(
                    session, rule, n, rule.config_json or {})
            elif rule.kind == "distribution_drift":
                col = rule.column_name
                if not col:
                    ok, detail = False, {"error": "drift requires a column"}
                else:
                    n = c.execute(select(func.count()).select_from(t)).scalar()
                    nulls = c.execute(
                        select(func.count()).select_from(t).where(
                            t.c[col].is_(None))).scalar()
                    values = [row[0] for row in c.execute(
                        select(t.c[col]).where(
                            t.c[col].isnot(None)).limit(10000)).fetchall()]
                    stats = _drift_stats(n, nulls, values)
                    ok, detail = _drift_result(
                        session, rule, stats, rule.config_json or {})
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


def delete_rule(session, project_id: int, rule_id: int) -> None:
    rule = (session.query(QualityRule)
            .filter_by(id=rule_id, project_id=project_id).first())
    if not rule:
        raise ValueError("rule not found")
    session.query(QualityResult).filter_by(rule_id=rule_id).delete(
        synchronize_session=False)
    session.delete(rule)
    session.commit()


def rule_summaries(session, project_id: int):
    rules = (session.query(QualityRule).filter_by(project_id=project_id)
             .order_by(QualityRule.id).all())
    out = []
    for rule in rules:
        results = (session.query(QualityResult)
                   .filter_by(rule_id=rule.id)
                   .order_by(QualityResult.at.desc(),
                             QualityResult.id.desc())
                   .limit(20).all())
        last = results[0] if results else None
        passed = sum(1 for r in results if r.status == "pass")
        out.append({
            "id": rule.id, "dataset_id": rule.dataset_id, "name": rule.name,
            "kind": rule.kind, "column": rule.column_name,
            "enabled": rule.enabled,
            "schedule_cron": rule.schedule_cron,
            "alert_on_fail": bool(rule.alert_on_fail),
            "sla_percent": (rule.config_json or {}).get("sla_percent"),
            "last_run_at": (rule.last_run_at.isoformat()
                            if rule.last_run_at else None),
            "last_status": last.status if last else None,
            "last_at": last.at.isoformat() if last else None,
            "pass_rate": (int(round(passed * 100 / len(results)))
                          if results else None),
        })
    return out


def trends(session, project_id, days=30):
    from datetime import datetime, timedelta, timezone
    days = max(1, min(int(days or 30), 180))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rules = (session.query(QualityRule)
             .filter_by(project_id=project_id)
             .order_by(QualityRule.id).all())
    daily = {}
    out = []
    for rule in rules:
        results = (session.query(QualityResult)
                   .filter(QualityResult.rule_id == rule.id,
                           QualityResult.at >= since)
                   .order_by(QualityResult.at.desc(),
                             QualityResult.id.desc()).all())
        passes = sum(1 for row in results if row.status == "pass")
        fails = len(results) - passes
        buckets = {}
        for row in results:
            day = row.at.date().isoformat() if row.at else ""
            bucket = buckets.setdefault(day, {"day": day, "pass": 0,
                                              "fail": 0})
            if row.status == "pass":
                bucket["pass"] += 1
            else:
                bucket["fail"] += 1
            overall = daily.setdefault(day, {"day": day, "pass": 0,
                                             "fail": 0})
            if row.status == "pass":
                overall["pass"] += 1
            else:
                overall["fail"] += 1
        streak = 0
        for row in results:
            if row.status == "pass":
                break
            streak += 1
        sla = (rule.config_json or {}).get("sla_percent")
        rate = int(round(passes * 100 / len(results))) if results else None
        out.append({
            "id": rule.id, "name": rule.name,
            "dataset_id": rule.dataset_id, "kind": rule.kind,
            "runs": len(results), "passes": passes, "fails": fails,
            "pass_rate": rate, "streak": streak,
            "sla_percent": sla,
            "below_sla": bool(sla is not None and rate is not None
                              and rate < int(sla)),
            "last_status": results[0].status if results else None,
            "series": [buckets[key] for key in sorted(buckets)]})
    return {"days": days,
            "daily": [daily[key] for key in sorted(daily)],
            "rules": out}


def check_sla(session, rule):
    sla = (rule.config_json or {}).get("sla_percent")
    if sla is None:
        return None
    try:
        sla = int(sla)
    except (TypeError, ValueError):
        return None
    if sla <= 0:
        return None
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (session.query(QualityResult)
            .filter(QualityResult.rule_id == rule.id,
                    QualityResult.at >= since).all())
    if not rows:
        return None
    passes = sum(1 for row in rows if row.status == "pass")
    rate = int(round(passes * 100 / len(rows)))
    if rate >= sla:
        return None
    from odf.services.alerts import raise_alert
    return raise_alert(
        session, rule.project_id, "warning",
        "quality SLA breach: %s" % rule.name,
        {"rule_id": rule.id, "pass_rate": rate, "sla_percent": sla,
         "runs": len(rows)})
