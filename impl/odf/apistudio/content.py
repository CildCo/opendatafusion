from odf.apistudio.catalog import table_columns
from odf.apistudio.compiler import (CompileError, compile_visual, render_sql)
from odf.apistudio.params import (ParamError, sample_values,
                                  validate_param_defs)
from odf.apistudio.sqlguard import SqlGuardError, ensure_read_only
from odf.models import Datasource


def empty_content():
    return {"mode": "visual", "query": None, "sql": None,
            "params": [], "auth": {"type": "aksk",
                                   "rate_limit_per_min": 60}}


def _err(field, message, parameter=None):
    out = {"field": field, "message": message}
    if parameter:
        out["parameter"] = parameter
    return out


def validate_content(session, content, project_id):
    errs = []
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    mode = content.get("mode")
    if mode not in ("visual", "sql"):
        errs.append(_err("mode", "mode must be visual or sql"))
    try:
        defs = validate_param_defs(content.get("params") or [])
    except ParamError as e:
        return [_err("params", str(e), e.parameter)]
    samples = sample_values(defs)
    if mode == "visual":
        query = content.get("query")
        if not isinstance(query, dict):
            errs.append(_err("query", "visual mode requires query"))
        else:
            ds_id = query.get("datasource_id")
            ds = session.get(Datasource, ds_id) if ds_id else None
            if not ds or ds.project_id != project_id:
                errs.append(_err("query.datasource_id",
                                 "datasource does not belong to project"))
            else:
                try:
                    columns = table_columns(session, ds, query.get("table"))
                    compile_visual(query, columns, samples)
                except (ValueError, CompileError) as e:
                    errs.append(_err("query", str(e)))
    elif mode == "sql":
        sql = content.get("sql")
        try:
            rendered, _ = render_sql(sql, defs, samples)
            ensure_read_only(rendered)
        except (CompileError, SqlGuardError) as e:
            errs.append(_err("sql", str(e)))
        ds_id = (content.get("query") or {}).get("datasource_id")
        ds = session.get(Datasource, ds_id) if ds_id else None
        if not ds or ds.project_id != project_id:
            errs.append(_err("datasource_id",
                             "datasource does not belong to project"))
        else:
            from odf.services.masking import datasource_has_policies
            if datasource_has_policies(session, ds.id):
                errs.append(_err(
                    "mode", "SQL mode is disabled for governed datasources; "
                    "use visual mode so column masks apply"))
    auth = content.get("auth")
    if auth is not None:
        if not isinstance(auth, dict) or auth.get("type") != "aksk":
            errs.append(_err("auth", "auth.type must be aksk"))
        else:
            allow = auth.get("ip_allowlist") or []
            import ipaddress
            if not isinstance(allow, list):
                errs.append(_err("auth.ip_allowlist",
                                 "ip_allowlist must be an array"))
            else:
                for item in allow:
                    try:
                        ipaddress.ip_network(item, strict=False)
                    except (TypeError, ValueError):
                        errs.append(_err("auth.ip_allowlist",
                                         "invalid CIDR: %s" % item))
            rate = auth.get("rate_limit_per_min")
            if rate is not None and (not isinstance(rate, int) or
                                     isinstance(rate, bool) or
                                     not 0 <= rate <= 100000):
                errs.append(_err("auth.rate_limit_per_min",
                                 "rate must be 0..100000"))
    return errs
