from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.appstudio.forms import form_schema, submit_form
from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import AssetVersion, AuditLog, Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "id"}, {"column": "city"}, {"column": "amount"}],
    "filters": [], "limit": 100},
    "params": [], "sql": None, "auth": None}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "w.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id integer primary key, "
                       "city text, amount int)"))
        c.execute(text("insert into t values (1, 'a', 10)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s, url


def _dataset(s):
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    return ds.id


def _app(s, dsid, forms):
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [{"id": cid, "type": "form", "dataset_id": dsid,
                        **comp} for cid, comp in forms.items()]}]}
    return create_asset(s, 1, "app", "A", content, "admin", enabled=False)


def _forms():
    return {
        "ins": {"mode": "insert", "fields": [
            {"column": "city", "widget": "input", "required": True},
            {"column": "amount", "widget": "number"}]},
        "upd": {"mode": "update", "key": "id", "fields": [
            {"column": "id", "widget": "number", "required": True},
            {"column": "city", "widget": "input"},
            {"column": "amount", "widget": "number"}]},
    }


def test_insert_and_update(tmp_path):
    s, url = _env(tmp_path)
    aid = _app(s, _dataset(s), _forms()).id
    out = submit_form(s, aid, "ins", {"city": "x", "amount": 3},
                      actor="u")
    assert out == {"ok": True, "mode": "insert", "affected": 1}
    out = submit_form(s, aid, "upd", {"id": 1, "city": "y"}, actor="u")
    assert out["affected"] == 1
    raw = create_engine(url)
    with raw.connect() as c:
        rows = c.execute(text("select id, city, amount from t order by id")
                         ).fetchall()
    assert rows == [(1, "y", 10), (2, "x", 3)]


def test_required_unknown_and_zero_row(tmp_path):
    s, _ = _env(tmp_path)
    aid = _app(s, _dataset(s), _forms()).id
    for values, needle in (
            ({"amount": 3}, "required"),
            ({"city": "x", "nope": 1}, "unknown"),
            ({"id": 999, "city": "x"}, "not found")):
        try:
            component = "upd" if "id" in values else "ins"
            submit_form(s, aid, component, values, actor="u")
        except ValueError as e:
            assert needle in str(e)
        else:
            raise AssertionError("expected error for %s" % values)


def test_multi_row_update_is_rolled_back(tmp_path):
    s, url = _env(tmp_path)
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("insert into t values (3, 'dup', 1), (4, 'dup', 2)"))
    dsid = _dataset(s)
    aid = _app(s, dsid, {"u": {
        "mode": "update", "key": "city", "fields": [
            {"column": "city", "widget": "input", "required": True},
            {"column": "amount", "widget": "number"}]}}).id
    try:
        submit_form(s, aid, "u", {"city": "dup", "amount": 9}, actor="u")
    except ValueError as e:
        assert "multiple" in str(e)
    else:
        raise AssertionError("multi-row update must fail")
    with raw.connect() as c:
        assert c.execute(text("select sum(amount) from t")).scalar() == 13


def test_audit_has_no_values_and_published_content(tmp_path):
    s, _ = _env(tmp_path)
    dsid = _dataset(s)
    a = _app(s, dsid, _forms())
    aid = a.id
    from odf.assets.service import update_draft
    v = s.get(AssetVersion, a.draft_version_id).content_json
    v["pages"][0]["components"] = [{"id": "ins", "type": "form",
                                    "dataset_id": dsid, "mode": "insert",
                                    "fields": [{"column": "amount",
                                                "widget": "number"}]}]
    update_draft(s, aid, v, "admin")
    publish_asset(s, aid, "admin")
    v["pages"][0]["components"] = [{"id": "ins", "type": "form",
                                    "dataset_id": dsid, "mode": "insert",
                                    "fields": [{"column": "city",
                                                "widget": "input"},
                                               {"column": "amount",
                                                "widget": "number"}]}]
    update_draft(s, aid, v, "admin")
    try:
        submit_form(s, aid, "ins", {"city": "secret"}, actor="u",
                    published_only=True)
    except ValueError as e:
        assert "unknown" in str(e)
    else:
        raise AssertionError("draft fields must not be used")
    out = submit_form(s, aid, "ins", {"amount": 7},
                      actor="u", published_only=True)
    out = submit_form(s, aid, "ins", {"amount": 8},
                      actor="u", published_only=True)
    assert out["affected"] == 1
    row = (s.query(AuditLog).filter_by(action="app_submit")
           .order_by(AuditLog.id.desc()).first())
    assert row.target == str(aid)
    assert "secret" not in str(row.detail_json)
    assert row.detail_json["mode"] == "insert"


def test_form_schema(tmp_path):
    s, _ = _env(tmp_path)
    dsid = _dataset(s)
    out = form_schema(s, 1, dsid)
    assert out["table"] == "t"
    assert out["columns"] == ["id", "city", "amount"]
    try:
        form_schema(s, 1, 999)
    except ValueError:
        pass
    else:
        raise AssertionError("missing dataset must fail")


def test_update_does_not_apply_defaults(tmp_path):
    s, url = _env(tmp_path)
    dsid = _dataset(s)
    aid = _app(s, dsid, {"u": {
        "mode": "update", "key": "id", "fields": [
            {"column": "id", "widget": "number", "required": True},
            {"column": "city", "widget": "input"},
            {"column": "amount", "widget": "number", "default": 99}]}}).id
    submit_form(s, aid, "u", {"id": 1, "city": "z"}, actor="u")
    raw = create_engine(url)
    with raw.connect() as c:
        assert c.execute(text("select amount from t where id=1")).scalar() == 10


def test_delete_form_removes_one_row(tmp_path):
    s, url = _env(tmp_path)
    dsid = _dataset(s)
    aid = _app(s, dsid, {"d": {
        "mode": "delete", "key": "id", "fields": [
            {"column": "id", "widget": "number", "required": True}]}}).id
    out = submit_form(s, aid, "d", {"id": 1}, actor="u", actor_role="admin")
    assert out == {"ok": True, "mode": "delete", "affected": 1}
    raw = create_engine(url)
    with raw.connect() as c:
        assert c.execute(text("select count(*) from t")).scalar() == 0


def test_delete_zero_and_multi_row(tmp_path):
    s, url = _env(tmp_path)
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("insert into t values (3, 'dup', 1), (4, 'dup', 2)"))
    dsid = _dataset(s)
    aid = _app(s, dsid, {"d": {
        "mode": "delete", "key": "city", "fields": [
            {"column": "city", "widget": "input", "required": True}]}}).id
    try:
        submit_form(s, aid, "d", {"city": "none"}, actor="u")
    except ValueError as e:
        assert "not found" in str(e)
    else:
        raise AssertionError("missing row must fail")
    try:
        submit_form(s, aid, "d", {"city": "dup"}, actor="u")
    except ValueError as e:
        assert "multiple" in str(e)
    else:
        raise AssertionError("multi-row delete must fail")
    with raw.connect() as c:
        assert c.execute(text("select count(*) from t where city='dup'")
                         ).scalar() == 2


def test_allow_roles_are_enforced(tmp_path):
    s, _ = _env(tmp_path)
    dsid = _dataset(s)
    aid = _app(s, dsid, {"ins": {
        "mode": "insert", "allow_roles": ["editor"],
        "fields": [{"column": "city", "widget": "input"}]}}).id
    try:
        submit_form(s, aid, "ins", {"city": "x"}, actor="v",
                    actor_role="viewer")
    except PermissionError:
        pass
    else:
        raise AssertionError("viewer must be denied")
    out = submit_form(s, aid, "ins", {"city": "x"}, actor="e",
                      actor_role="editor")
    assert out["affected"] == 1


def test_delete_is_audited(tmp_path):
    s, _ = _env(tmp_path)
    dsid = _dataset(s)
    aid = _app(s, dsid, {"d": {
        "mode": "delete", "key": "id", "fields": [
            {"column": "id", "widget": "number", "required": True}]}}).id
    submit_form(s, aid, "d", {"id": 1}, actor="u", actor_role="admin")
    row = (s.query(AuditLog).filter_by(action="app_submit")
           .order_by(AuditLog.id.desc()).first())
    assert row.target == str(aid)
    assert row.detail_json["mode"] == "delete"
    assert "1" not in str(row.detail_json.get("values"))
