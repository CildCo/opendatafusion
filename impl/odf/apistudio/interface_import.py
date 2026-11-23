import json

from sqlalchemy import text

from odf.models import Asset, AssetVersion


def _rows(session):
    rows = session.execute(text(
        "select id, project_id, datasource_id, interface_key, name, "
        "sql_text, params_json, output_json, status from data_interface "
        "order by id")).mappings().all()
    for row in rows:
        value = row["params_json"]
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                value = []
        yield {**row, "params_json": value or []}


def import_interface_records(session, commit=True):
    count = 0
    for i in _rows(session):
        if session.query(Asset).filter_by(key=i["interface_key"]).first():
            continue
        a = Asset(project_id=i["project_id"], type="api",
                  key=i["interface_key"], name=i["name"], description="",
                  owner="system", enabled=(i["status"] == 1))
        session.add(a)
        session.flush()
        content = {"mode": "sql",
                   "query": {"datasource_id": i["datasource_id"]},
                   "sql": i["sql_text"],
                   "params": i["params_json"] or [],
                   "auth": {"type": "aksk", "rate_limit_per_min": 60}}
        v = AssetVersion(asset_id=a.id, version=1, content_json=content,
                         status="published", created_by="system",
                         note="imported from interface record %s" % i["id"])
        session.add(v)
        session.flush()
        a.draft_version_id = v.id
        a.published_version_id = v.id
        count += 1
    if commit:
        session.commit()
    else:
        session.flush()
    return count
