import re
from datetime import datetime, timezone

from sqlalchemy import inspect

from odf.assets.service import get_asset
from odf.models import Asset, AssetVersion, ContractCheck, Datasource
from odf.services.query import execute_query

_TYPE_PARAMS = re.compile(r"\(.*\)")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _asset(session, project_id, asset_id):
    asset = get_asset(session, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    if asset.type not in ("dataset", "model"):
        raise ValueError("contracts are supported for datasets and models")
    return asset


def _content(session, asset):
    version_id = asset.published_version_id or asset.draft_version_id
    version = session.get(AssetVersion, version_id) if version_id else None
    if not version:
        raise ValueError("asset content not found")
    return version.content_json or {}


def _actual_columns(session, asset, content):
    if asset.type == "dataset":
        query = content.get("query") or {}
        datasource = session.get(Datasource, query.get("datasource_id")) \
            if isinstance(query.get("datasource_id"), int) else None
        table = query.get("table")
        if not datasource or not table:
            raise ValueError("dataset has no physical table")
        from odf.apistudio.catalog import table_column_info
        columns = table_column_info(session, datasource, table)
        return [{"name": item["name"], "type": item.get("type") or ""}
                for item in columns], table, datasource
    from odf.transform.service import target_for
    datasource = session.get(Datasource, content.get("datasource_id")) \
        if isinstance(content.get("datasource_id"), int) else None
    if not datasource:
        raise ValueError("model datasource not found")
    target, _, schema = target_for(session, asset, content)
    if datasource.kind == "trino":
        result = execute_query(session, datasource, "DESCRIBE " + target,
                               {}, 500)
        columns = []
        for row in result["rows"]:
            values = list(row.values())
            if len(values) >= 2:
                columns.append({"name": str(values[0]),
                                "type": str(values[1])})
        return columns, target, datasource
    from odf.services.connections import engine_for
    with engine_for(datasource) as engine:
        inspector = inspect(engine)
        kwargs = {}
        if schema and datasource.kind not in ("sqlite", "duckdb"):
            kwargs["schema"] = schema
        try:
            columns = inspector.get_columns(asset.key, **kwargs)
        except Exception:
            raise ValueError("model target table not found")
    return [{"name": item["name"], "type": str(item["type"])}
            for item in columns], target, datasource


def _clean_type(value):
    text = _TYPE_PARAMS.sub("", str(value or "")).strip().lower()
    return re.sub(r"\s+", " ", text)


def _same_type(expected, actual):
    left, right = _clean_type(expected), _clean_type(actual)
    if not left or not right:
        return True
    return left == right or left.startswith(right) or right.startswith(left)


def expected_columns(contract):
    out = []
    for item in (contract or {}).get("schema") or []:
        if isinstance(item, str):
            out.append({"name": item, "type": ""})
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            out.append({"name": item["name"],
                        "type": str(item.get("type") or "")})
    return out


def _as_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _freshness_issues(session, datasource, target, config):
    column = config.get("column")
    hours = int(config.get("max_hours") or 0)
    if not isinstance(column, str) or not _IDENT.match(column):
        return [{"kind": "freshness", "column": str(column or ""),
                 "expected": "", "actual": "invalid column"}]
    from odf.apistudio.compiler import quote_ident
    try:
        result = execute_query(
            session, datasource,
            "SELECT MAX(%s) AS latest FROM %s"
            % (quote_ident(column), target), {}, 1)
    except ValueError:
        return [{"kind": "freshness", "column": column,
                 "expected": "", "actual": "column unavailable"}]
    value = None
    if result.get("rows"):
        value = next(iter(result["rows"][0].values()), None)
    latest = _as_datetime(value)
    if latest is None:
        return [{"kind": "stale", "column": column,
                 "expected": "within %dh" % hours,
                 "actual": "no data" if value is None else "not a time"}]
    age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
    if age_hours > hours:
        return [{"kind": "stale", "column": column,
                 "expected": "within %dh" % hours,
                 "actual": "%.1fh old" % age_hours}]
    return []


def _quality_issues(session, datasource, target, contract):
    from odf.apistudio.compiler import quote_ident
    issues = []
    for check in contract.get("quality") or []:
        if not isinstance(check, dict):
            continue
        kind = check.get("kind")
        column = check.get("column")
        expected = ""
        try:
            if kind == "not_null":
                expected = "no nulls"
                sql = "SELECT COUNT(*) FROM %s WHERE %s IS NULL" % (
                    target, quote_ident(column))
                params = {}
            elif kind == "unique":
                expected = "no duplicates"
                sql = ("SELECT COUNT(*) - COUNT(DISTINCT %s) FROM %s"
                       % (quote_ident(column), target))
                params = {}
            elif kind == "accepted_values":
                expected = "accepted values"
                binds, keys = {}, []
                for index, value in enumerate(check.get("values") or []):
                    key = "v%d" % index
                    binds[key] = value
                    keys.append(":" + key)
                sql = ("SELECT COUNT(*) FROM %s WHERE %s IS NOT NULL "
                       "AND %s NOT IN (%s)"
                       % (target, quote_ident(column), quote_ident(column),
                          ", ".join(keys)))
                params = binds
            elif kind == "max_null_pct":
                limit = int(check.get("max_null_pct") or 0)
                expected = "null rate <= %d%%" % limit
                sql = ("SELECT COUNT(*) AS total, COUNT(%s) AS present "
                       "FROM %s" % (quote_ident(column), target))
                params = {}
            elif kind == "sql":
                expected = "custom check returns zero"
                sql = check.get("sql") or ""
                params = {}
            else:
                continue
            result = execute_query(session, datasource, sql, params, 1)
            row = result.get("rows") or [{}]
            values = list(row[0].values()) if row else []
            if kind == "max_null_pct":
                total = int(values[0] or 0) if values else 0
                present = int(values[1] or 0) if len(values) > 1 else 0
                actual = 0 if total == 0 else                     round((total - present) * 100 / total)
                if actual > int(check.get("max_null_pct") or 0):
                    issues.append({"kind": "quality", "column": column,
                                   "expected": expected,
                                   "actual": "%d%%" % actual})
                continue
            value = int(values[0] or 0) if values else 0
            if value > 0:
                issues.append({"kind": "quality", "column": column,
                               "expected": expected,
                               "actual": "%d failing rows" % value})
        except Exception:
            issues.append({"kind": "quality", "column": column or "",
                           "expected": expected, "actual": "unavailable"})
    return issues


def check_asset(session, project_id, asset_id, content=None):
    asset = _asset(session, project_id, asset_id)
    content = content if content is not None else _content(session, asset)
    actual, target, datasource = _actual_columns(session, asset, content)
    contract = asset.contract_json or {}
    expected = expected_columns(contract)
    actual_by_name = {item["name"].lower(): item for item in actual}
    expected_names = {item["name"].lower() for item in expected}
    issues = []
    for item in expected:
        found = actual_by_name.get(item["name"].lower())
        if not found:
            issues.append({"kind": "missing", "column": item["name"],
                           "expected": item.get("type") or "",
                           "actual": ""})
        elif item.get("type") and not _same_type(item["type"],
                                                 found["type"]):
            issues.append({"kind": "type", "column": item["name"],
                           "expected": item["type"],
                           "actual": found["type"]})
    freshness = contract.get("freshness")
    if freshness:
        issues.extend(_freshness_issues(session, datasource, target,
                                        freshness))
    issues.extend(_quality_issues(session, datasource, target, contract))
    if contract.get("allow_extra") is False:
        for item in actual:
            if item["name"].lower() not in expected_names:
                issues.append({"kind": "unexpected", "column": item["name"],
                               "expected": "", "actual": item["type"]})
    return {"asset_id": asset.id, "asset_type": asset.type,
            "name": asset.name, "target": target, "ok": not issues,
            "expected": len(expected), "actual": len(actual),
            "issues": issues,
            "checked_at": datetime.now(timezone.utc)}


def generate_contract(session, project_id, asset_id):
    asset = _asset(session, project_id, asset_id)
    content = _content(session, asset)
    actual, _, _ = _actual_columns(session, asset, content)
    contract = dict(asset.contract_json or {})
    contract["schema"] = [{"name": item["name"], "type": item["type"],
                           "required": False} for item in actual]
    from odf.services.governance import _clean_contract
    asset.contract_json = _clean_contract(contract)
    session.commit()
    session.refresh(asset)
    return asset.contract_json


def schedule_of(contract):
    value = (contract or {}).get("schedule")
    return value.strip() if isinstance(value, str) and value.strip() else ""


def due_schedules(session, now):
    from odf.services.scheduler import cron_to_trigger, project_timezone
    assets = (session.query(Asset)
              .filter(Asset.type.in_(("dataset", "model")),
                      Asset.contract_json.isnot(None)).all())
    out = []
    for asset in assets:
        schedule = schedule_of(asset.contract_json)
        if not schedule:
            continue
        try:
            trigger = cron_to_trigger(
                schedule, project_timezone(session, asset.project_id))
        except Exception:
            continue
        last = (session.query(ContractCheck)
                .filter_by(asset_id=asset.id)
                .order_by(ContractCheck.checked_at.desc()).first())
        if last and last.checked_at:
            stamp = last.checked_at
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            nxt = trigger.get_next_fire_time(None, stamp)
            if nxt is not None:
                if nxt.tzinfo is None:
                    nxt = nxt.replace(tzinfo=timezone.utc)
                if nxt > now:
                    continue
        out.append(asset)
    return out


def save_check(session, asset, result):
    row = ContractCheck(
        project_id=asset.project_id, asset_id=asset.id,
        status="ok" if result.get("ok") else "failed",
        issues_json=result.get("issues") or [])
    session.add(row)
    session.commit()
    return row


def checks(session, project_id, asset_id, limit=20):
    asset = _asset(session, project_id, asset_id)
    limit = max(1, min(int(limit or 20), 100))
    rows = (session.query(ContractCheck)
            .filter_by(asset_id=asset.id)
            .order_by(ContractCheck.id.desc()).limit(limit).all())
    return [{"id": row.id, "status": row.status,
             "issues": row.issues_json or [],
             "checked_at": row.checked_at} for row in rows]


def contract_summaries(session, project_id, include_missing=False):
    from odf.models import Asset
    rows = (session.query(Asset)
            .filter(Asset.project_id == project_id)
            .filter(Asset.type.in_(("dataset", "model")))
            .order_by(Asset.id.desc()).all())
    out = []
    for asset in rows:
        contract = asset.contract_json or {}
        if not contract and not include_missing:
            continue
        last = (session.query(ContractCheck)
                .filter_by(asset_id=asset.id)
                .order_by(ContractCheck.id.desc()).first())
        out.append({"asset_id": asset.id, "asset_type": asset.type,
                    "schedule": schedule_of(contract),
                    "last_check": {"status": last.status,
                                   "checked_at": last.checked_at}
                    if last else None,
                    "name": asset.name, "key": asset.key,
                    "has_contract": bool(contract),
                    "enforce": bool(contract.get("enforce")),
                    "allow_extra": contract.get("allow_extra") is not False,
                    "columns": len(contract.get("schema") or []),
                    "owner": contract.get("owner") or asset.owner,
                    "sla": contract.get("sla") or "",
                    "freshness": contract.get("freshness") or {},
                    "quality": contract.get("quality") or [],
                    "updated_at": asset.updated_at})
    return out
