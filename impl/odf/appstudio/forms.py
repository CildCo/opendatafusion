from datetime import date, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from odf.apistudio.compiler import CompileError, quote_ident, quote_table
from odf.appstudio.content import (FORM_ROLES, _published,
                                   dataset_physical_columns,
                                   structural_errors, validate_component)
from odf.assets.service import get_asset
from odf.modelstudio.content import validate_dataset
from odf.models import AssetVersion
from odf.services.audit import write_audit
from odf.services.datasource import connect_args_for, get_dsn, prepare_connection
from odf.settings import get_settings


def _version_content(session, asset, published_only):
    vid = asset.published_version_id if published_only \
        else (asset.draft_version_id or asset.published_version_id)
    v = session.get(AssetVersion, vid) if vid else None
    if not v:
        raise ValueError("content not found")
    return v.content_json


def form_schema(session, project_id, dataset_id):
    ds_content, err = _published(session, dataset_id, "dataset", project_id)
    if err:
        raise ValueError(err["message"])
    if validate_dataset(session, ds_content, project_id):
        raise ValueError("dataset is invalid")
    _, table, columns = dataset_physical_columns(session, ds_content)
    return {"table": table, "columns": columns}


def _coerce(field, raw):
    if raw is None or raw == "":
        return None
    widget = field.get("widget")
    if widget in ("input", "textarea"):
        return str(raw)
    if widget == "select":
        value = str(raw)
        if value not in (field.get("options") or []):
            raise ValueError("invalid option for %s" % field["column"])
        return value
    if widget == "number":
        if isinstance(raw, bool):
            raise ValueError("%s must be a number" % field["column"])
        try:
            number = float(raw)
        except (TypeError, ValueError):
            raise ValueError("%s must be a number" % field["column"])
        return int(number) if number.is_integer() else number
    if widget == "checkbox":
        if isinstance(raw, bool):
            return raw
        text_value = str(raw).strip().lower()
        if text_value in ("1", "true", "t", "yes", "y"):
            return True
        if text_value in ("0", "false", "f", "no", "n"):
            return False
        raise ValueError("%s must be a boolean" % field["column"])
    if widget == "date":
        if isinstance(raw, (date, datetime)):
            return raw.isoformat()
        value = str(raw)
        try:
            if "T" in value or " " in value:
                datetime.fromisoformat(value)
            else:
                date.fromisoformat(value)
        except ValueError:
            raise ValueError("%s must be an ISO date" % field["column"])
        return value
    raise ValueError("unsupported widget: %s" % widget)


def _values_for(fields, payload, apply_defaults=True):
    if not isinstance(payload, dict):
        raise ValueError("values must be an object")
    by_col = {f["column"]: f for f in fields}
    unknown = set(payload) - set(by_col)
    if unknown:
        raise ValueError("unknown columns: %s" % ", ".join(sorted(unknown)))
    out = {}
    for column, field in by_col.items():
        if column in payload:
            raw = payload[column]
        elif apply_defaults:
            raw = field.get("default")
        else:
            continue
        value = _coerce(field, raw)
        if value is None:
            if field.get("required"):
                raise ValueError("field %s is required" % column)
            continue
        out[column] = value
    return out


def _engine(dsn, kind=None):
    return create_engine(dsn, connect_args=connect_args_for(kind or "", dsn))


def submit_form(session, asset_id, component_id, values,
                published_only=False, actor="", actor_role="viewer"):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "app":
        raise ValueError("app not found")
    content = _version_content(session, asset, published_only)
    errs = structural_errors(content)
    if errs:
        raise ValueError("invalid app: %s" % errs)
    comp = page = None
    for p in content["pages"]:
        for c in p.get("components") or []:
            if c.get("id") == component_id and c.get("type") == "form":
                comp, page = c, p
                break
        if comp:
            break
    if not comp:
        raise ValueError("form component not found")
    errs = validate_component(session, page, comp, asset.project_id)
    if errs:
        raise ValueError("invalid form: %s" % errs)
    if actor_role not in (comp.get("allow_roles") or FORM_ROLES):
        raise PermissionError("role cannot submit this form")
    fields = comp["fields"]
    mode = comp.get("mode")
    out = _values_for(fields, values, apply_defaults=(mode == "insert"))
    if mode in ("update", "delete"):
        key = comp["key"]
        if key not in out:
            raise ValueError("key is required")
        if mode == "update" and not [c for c in out if c != key]:
            raise ValueError("no fields to update")
    elif not out:
        raise ValueError("no values to insert")

    ds_content, err = _published(session, comp["dataset_id"], "dataset",
                                 asset.project_id)
    if err:
        raise ValueError(err["message"])
    ds, table, columns = dataset_physical_columns(session, ds_content)
    if any(c not in columns for c in out):
        raise ValueError("column not in table")

    binds = {"v%d" % i: v for i, v in enumerate(out.values())}
    try:
        if mode == "insert":
            cols = list(out)
            names = [quote_ident(c) for c in cols]
            keys = ["v%d" % i for i in range(len(cols))]
            sql = "INSERT INTO %s (%s) VALUES (%s)" % (
                quote_table(table), ", ".join(names), ", ".join(":" + k
                                                                for k in keys))
        elif mode == "delete":
            key = comp["key"]
            binds["k0"] = out[key]
            sql = "DELETE FROM %s WHERE %s = :k0" % (
                quote_table(table), quote_ident(key))
        else:
            key = comp["key"]
            set_cols = [c for c in out if c != key]
            assignments = ", ".join("%s = :%s" % (quote_ident(c),
                                                  "v%d" % list(out).index(c))
                                    for c in set_cols)
            key_bind = "k0"
            binds[key_bind] = out[key]
            sql = "UPDATE %s SET %s WHERE %s = :%s" % (
                quote_table(table), assignments, quote_ident(key), key_bind)
    except CompileError as e:
        raise ValueError(str(e))

    settings = get_settings()
    try:
        engine = _engine(get_dsn(ds), ds.kind)
        with engine.begin() as c:
            prepare_connection(c, engine.dialect.name,
                               settings.query_timeout_s * 1000)
            result = c.execute(text(sql), binds)
            affected = result.rowcount or 0
            if mode == "insert" and affected != 1:
                raise ValueError("insert failed")
            if mode in ("update", "delete"):
                if affected == 0:
                    raise ValueError("record not found")
                if affected > 1:
                    raise ValueError("key matched multiple rows")
    except ValueError:
        raise
    except SQLAlchemyError:
        raise ValueError("submit failed")

    write_audit(session, actor, "app_submit", str(asset.id),
                {"component_id": component_id, "mode": mode,
                 "affected": affected})
    from odf.webhooks.service import emit_safe
    emit_safe(session, asset.project_id, "app.submitted",
              {"asset_id": asset.id, "component_id": component_id,
               "mode": mode, "affected": affected})
    return {"ok": True, "mode": mode, "affected": affected}
