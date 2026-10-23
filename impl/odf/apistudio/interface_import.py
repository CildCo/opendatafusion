from odf.models import Asset, AssetVersion, Interface


def import_interface_records(session, commit=True):
    count = 0
    for i in session.query(Interface).order_by(Interface.id).all():
        if session.query(Asset).filter_by(key=i.interface_key).first():
            continue
        a = Asset(project_id=i.project_id, type="api", key=i.interface_key,
                  name=i.name, description="", owner="system",
                  enabled=(i.status == 1))
        session.add(a)
        session.flush()
        content = {"mode": "sql",
                   "query": {"datasource_id": i.datasource_id},
                   "sql": i.sql_text,
                   "params": i.params_json or [],
                   "auth": {"type": "aksk", "rate_limit_per_min": 60}}
        v = AssetVersion(asset_id=a.id, version=1, content_json=content,
                         status="published", created_by="system",
                         note="imported from interface record %s" % i.id)
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
