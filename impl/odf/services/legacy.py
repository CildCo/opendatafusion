def migrate_flow(session, project_id: int, flow_id: int, actor: str):
    from odf.assets.service import create_asset
    from odf.models import Asset, Datasource, Flow, FlowVersion
    from odf.services.notifications import notify
    flow = session.get(Flow, flow_id)
    if not flow or flow.project_id != project_id:
        raise ValueError("flow not found")
    if flow.migrated_asset_id:
        existing = session.get(Asset, flow.migrated_asset_id)
        if existing and existing.project_id == project_id:
            return existing
    version = (session.query(FlowVersion)
               .filter_by(flow_id=flow.id, version=flow.current_version)
               .first())
    if not version:
        raise ValueError("flow version not found")
    dag = version.dag_json or {}
    required = ("source_ds_id", "sink_ds_id", "source_table", "sink_table")
    if not all(dag.get(key) for key in required):
        raise ValueError("flow is missing source or sink settings")
    for key in ("source_ds_id", "sink_ds_id"):
        ds = session.get(Datasource, dag[key])
        if not ds or ds.project_id != project_id:
            raise ValueError("flow datasource does not belong to project")
    source_config = {
        "datasource_id": dag["source_ds_id"],
        "table": dag["source_table"],
        "cursor_column": dag.get("cursor_column") or "",
        "pk": dag.get("pk") or "id",
    }
    sink_config = {
        "datasource_id": dag["sink_ds_id"],
        "table": dag["sink_table"],
        "mode": dag.get("mode") or "upsert",
        "pk": dag.get("pk") or ["id"],
    }
    content = {
        "nodes": [
            {"id": "source_1", "type": "source",
             "position": {"x": 80, "y": 120}, "name": "源",
             "config": source_config},
            {"id": "sink_1", "type": "sink",
             "position": {"x": 420, "y": 120}, "name": "目标",
             "config": sink_config},
        ],
        "edges": [{"id": "e1", "source": "source_1", "target": "sink_1"}],
        "settings": {"batch": int(dag.get("batch") or 1000)},
    }
    asset = create_asset(session, project_id, "pipeline", flow.name,
                         content, actor, enabled=False)
    asset.cron = flow.cron or None
    flow.status = 0
    flow.migrated_asset_id = asset.id
    session.commit()
    notify(session, project_id, "migration",
           "数据集成已迁移为管道：%s" % flow.name,
           "请检查管道配置并发布", "/pipelines/%d" % asset.id)
    return asset


def migrate_interface(session, project_id: int, interface_id: int,
                      actor: str):
    from odf.apistudio.content import empty_content
    from odf.assets.service import create_asset
    from odf.models import Asset, Datasource, Interface
    from odf.services.notifications import notify
    row = session.get(Interface, interface_id)
    if not row or row.project_id != project_id:
        raise ValueError("interface not found")
    if row.migrated_asset_id:
        existing = session.get(Asset, row.migrated_asset_id)
        if existing and existing.project_id == project_id:
            return existing
    ds = session.get(Datasource, row.datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("interface datasource does not belong to project")
    content = empty_content()
    content.update({
        "mode": "sql",
        "query": {"datasource_id": row.datasource_id},
        "sql": row.sql_text,
        "params": row.params_json or [],
    })
    key = row.interface_key
    if session.query(Asset).filter_by(key=key).first():
        key = None
    asset = create_asset(session, project_id, "api", row.name, content,
                         actor, key=key, enabled=False)
    row.status = 0
    row.migrated_asset_id = asset.id
    session.commit()
    notify(session, project_id, "migration",
           "接口已迁移为 API：%s" % row.name,
           "请检查 API 配置并发布", "/apis/%d" % asset.id)
    return asset
