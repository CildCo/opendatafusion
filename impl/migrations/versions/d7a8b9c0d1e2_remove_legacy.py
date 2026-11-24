"""remove legacy flows and interfaces

Revision ID: d7a8b9c0d1e2
Revises: c6f7a8b9c0d1
Create Date: 2026-11-24
"""
import json
import secrets

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import Session

from odf.models import Asset, AssetVersion, Notification

revision = "d7a8b9c0d1e2"
down_revision = "c6f7a8b9c0d1"
branch_labels = None
depends_on = None


def _json(value):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return {}


def _key(session, prefix):
    while True:
        key = "%s_%s" % (prefix, secrets.token_hex(4))
        found = session.execute(
            text("select 1 from asset where key=:key"), {"key": key}).first()
        if not found:
            return key


def _notify(session, project_id, title, body, link):
    values = {}
    if session.bind.dialect.name == "sqlite":
        values["id"] = session.execute(text(
            "select coalesce(max(id), 0) + 1 from notification")).scalar()
    session.add(Notification(project_id=project_id, kind="migration",
                             title=title[:200], body=body,
                             link=link[:256], **values))


def _flow_content(dag):
    required = ("source_ds_id", "sink_ds_id", "source_table", "sink_table")
    if not all(dag.get(key) for key in required):
        return None
    pk = dag.get("pk") or "id"
    sink_pk = pk if isinstance(pk, list) else [pk]
    return {
        "nodes": [
            {"id": "source_1", "type": "source", "name": "源",
             "position": {"x": 80, "y": 120},
             "config": {"datasource_id": dag["source_ds_id"],
                        "table": dag["source_table"],
                        "cursor_column": dag.get("cursor_column") or "",
                        "pk": pk}},
            {"id": "sink_1", "type": "sink", "name": "目标",
             "position": {"x": 420, "y": 120},
             "config": {"datasource_id": dag["sink_ds_id"],
                        "table": dag["sink_table"],
                        "mode": dag.get("mode") or "upsert",
                        "pk": sink_pk}},
        ],
        "edges": [{"id": "e1", "from": "source_1", "to": "sink_1"}],
        "settings": {"batch": int(dag.get("batch") or 1000)},
    }


def _publishable(session, kind, content, project_id):
    try:
        if kind == "pipeline":
            from odf.pipeline.validate import validate_pipeline_content
            return not validate_pipeline_content(session, content, project_id)
        from odf.apistudio.content import validate_content
        return not validate_content(session, content, project_id)
    except Exception:
        return False


def _add(session, project_id, kind, name, content, enabled, published,
         key, note):
    asset = Asset(project_id=project_id, type=kind, key=key, name=name,
                  description="从旧版模块自动迁移", owner="system",
                  enabled=bool(published))
    session.add(asset)
    session.flush()
    version = AssetVersion(asset_id=asset.id, version=1,
                           content_json=content,
                           status="published" if published else "draft",
                           created_by="system", note=note)
    session.add(version)
    session.flush()
    asset.draft_version_id = version.id
    if published:
        asset.published_version_id = version.id
    return asset


def _migrate_flows(session):
    rows = session.execute(text(
        "select id, project_id, name, cron, status, current_version, "
        "migrated_asset_id from flow")).mappings().all()
    for row in rows:
        if row["migrated_asset_id"]:
            existing = session.get(Asset, row["migrated_asset_id"])
            if existing:
                continue
        dag_row = session.execute(text(
            "select dag_json from flow_version where flow_id=:id and "
            "version=:v"), {"id": row["id"], "v": row["current_version"]}
        ).first()
        dag = _json(dag_row[0] if dag_row else {})
        content = _flow_content(dag)
        published = bool(content is not None and row["status"] == 1)
        if content is None:
            content = {"nodes": [], "edges": [], "settings": {}}
        asset = _add(session, row["project_id"], "pipeline", row["name"],
                     content, row["status"] == 1, published,
                     _key(session, "pipeline"),
                     "migrated from flow %s" % row["id"])
        asset.cron = row["cron"] or None
        if published:
            title = "旧版数据集成已迁移并发布：%s" % row["name"]
            body = "已转换为数据管道，继续按原计划运行"
            link = "/pipelines/%d" % asset.id
        else:
            title = "旧版数据集成已迁移为草稿：%s" % row["name"]
            body = "请在数据管道中检查配置并发布"
            link = "/pipelines/%d" % asset.id
        _notify(session, row["project_id"], title, body, link)


def _migrate_interfaces(session):
    rows = session.execute(text(
        "select id, project_id, datasource_id, interface_key, name, "
        "sql_text, params_json, status from data_interface")).mappings().all()
    for row in rows:
        if session.execute(text("select 1 from asset where key=:k"),
                           {"k": row["interface_key"]}).first():
            continue
        params = _json(row["params_json"])
        content = {"mode": "sql",
                   "query": {"datasource_id": row["datasource_id"]},
                   "sql": row["sql_text"],
                   "params": params if isinstance(params, list) else [],
                   "auth": {"type": "aksk", "rate_limit_per_min": 60}}
        published = False
        if row["status"] == 1:
            published = _publishable(session, "api", content,
                                     row["project_id"])
        asset = _add(session, row["project_id"], "api", row["name"], content,
                     row["status"] == 1, published,
                     row["interface_key"],
                     "migrated from data_interface %s" % row["id"])
        if not published and row["status"] == 1:
            title = "旧版 SQL 接口已迁移为草稿：%s" % row["name"]
            body = "接口需要检查 SQL 或数据源策略后重新发布"
        elif published:
            title = "旧版 SQL 接口已迁移并发布：%s" % row["name"]
            body = "原调用地址与密钥继续可用"
        else:
            title = "旧版 SQL 接口已迁移为草稿：%s" % row["name"]
            body = "接口尚未发布，可在数据 API 中继续处理"
        _notify(session, row["project_id"], title, body,
                "/apis/%d" % asset.id)


def upgrade():
    session = Session(bind=op.get_bind())
    _migrate_flows(session)
    _migrate_interfaces(session)
    session.execute(text(
        "delete from job_dependency where downstream_type='flow' "
        "or upstream_type='flow'"))
    session.execute(text("delete from job where flow_id is not null"))
    session.execute(text(
        "delete from change_request where action like '%_flow' "
        "or action like '%_interface'"))
    session.commit()
    session.close()

    with op.batch_alter_table("job") as batch:
        batch.drop_index("ix_job_flow_id")
        batch.drop_column("flow_id")
    op.drop_table("health_event")
    op.drop_table("flow_run")
    op.drop_table("flow_version")
    op.drop_table("flow")
    op.drop_table("data_interface")


def downgrade():
    op.create_table(
        "flow",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("cron", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("migrated_asset_id", sa.Integer(), nullable=True),
    )
    op.create_table(
        "flow_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flow_id", sa.Integer(), sa.ForeignKey("flow.id"),
                  nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dag_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "flow_run",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("flow_id", sa.Integer(), sa.ForeignKey("flow.id"),
                  nullable=False, index=True),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_num", sa.BigInteger(), nullable=False),
        sa.Column("out_num", sa.BigInteger(), nullable=False),
        sa.Column("err_num", sa.BigInteger(), nullable=False),
        sa.Column("cursor_value", sa.String(length=256), nullable=True),
    )
    op.create_table(
        "health_event",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("flow_id", sa.Integer(), sa.ForeignKey("flow.id"),
                  nullable=False, index=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "data_interface",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False, index=True),
        sa.Column("datasource_id", sa.Integer(),
                  sa.ForeignKey("datasource.id"), nullable=False),
        sa.Column("interface_key", sa.String(length=64), nullable=False,
                  unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("migrated_asset_id", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("job") as batch:
        batch.add_column(sa.Column("flow_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_job_flow_id", "flow", ["flow_id"], ["id"])
