import re

from odf.assets.service import create_asset
from odf.connectors.registry import supports
from odf.models import Datasource

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")

TEMPLATES = [
    {"id": "model-staging", "type": "model", "mode": "model",
     "title": "标准 staging 模型",
     "title_en": "Standard staging model",
     "description": "整表落地到 staging 层，适合作为后续模型的输入。",
     "description_en": "Lands the source table in the staging layer for downstream models.",
     "content": {"materialization": "table", "layer": "staging",
                 "sql": "select * from {table}"}},
    {"id": "model-merge", "type": "model", "mode": "model",
     "title": "增量合并模型",
     "title_en": "Incremental merge model",
     "description": "按键合并更新，适合有主键的变更表。",
     "description_en": "Merges rows by key; suits change tables with a primary key.",
     "content": {"materialization": "incremental", "layer": "staging",
                 "unique_key": ["id"], "incremental_strategy": "merge",
                 "sql": "select * from {table}"}},
    {"id": "model-dedup", "type": "model", "mode": "model",
     "title": "去重宽表",
     "title_en": "Deduplicated mart",
     "description": "对源表去重后落到 mart 层。",
     "description_en": "Deduplicates the source table into the mart layer.",
     "content": {"materialization": "table", "layer": "mart",
                 "sql": "select distinct * from {table}"}},
    {"id": "pipeline-copy", "type": "pipeline", "mode": "pipeline",
     "title": "表同步管道",
     "title_en": "Table sync pipeline",
     "description": "把源表按主键 upsert 到目标表。",
     "description_en": "Upserts the source table into a target table by primary key.",
     "content": {"mode": "upsert"}},
    {"id": "app-approval", "type": "app", "mode": "app",
     "title": "审批工作台",
     "title_en": "Approval workbench",
     "description": "集中查看并处理项目待审批事项。",
     "description_en": "Review and apply pending project approvals.",
     "content": {"start_page": "p1", "pages": [{
         "id": "p1", "title": "审批", "params": [], "components": [
             {"id": "h", "type": "heading", "text": "待审批事项",
              "layout": {"x": 0, "y": 0, "w": 12, "h": 2}},
             {"id": "q", "type": "approval", "title": "待审批",
              "limit": 10, "layout": {"x": 0, "y": 2, "w": 12, "h": 8}}]}]}},
    {"id": "app-upload", "type": "app", "mode": "app",
     "title": "文件收集",
     "title_en": "File intake",
     "description": "提供一个受控的文件上传入口。",
     "description_en": "Collect files through a controlled upload page.",
     "content": {"start_page": "p1", "pages": [{
         "id": "p1", "title": "上传", "params": [], "components": [
             {"id": "h", "type": "heading", "text": "上传文件",
              "layout": {"x": 0, "y": 0, "w": 12, "h": 2}},
             {"id": "u", "type": "upload", "label": "选择文件",
              "accept": ["csv", "xlsx", "pdf"], "max_mb": 20,
              "layout": {"x": 0, "y": 2, "w": 6, "h": 4}}]}]}},
]


def list_templates(type=None):
    out = []
    for row in TEMPLATES:
        if type and row["type"] != type:
            continue
        out.append({key: row[key]
                    for key in ("id", "type", "mode", "title", "title_en",
                                "description", "description_en")})
    return out


def _template(template_id):
    for row in TEMPLATES:
        if row["id"] == template_id:
            return row
    raise ValueError("template not found")


def _datasource(session, project_id, datasource_id, capability):
    datasource = session.get(Datasource, datasource_id) \
        if isinstance(datasource_id, int) else None
    if not datasource or datasource.project_id != project_id:
        raise ValueError("datasource not found")
    if not supports(datasource.kind, capability):
        raise ValueError("%s does not support %s" % (datasource.kind,
                                                     capability))
    return datasource


def _table(value):
    text = str(value or "").strip()
    if not _TABLE.match(text):
        raise ValueError("invalid table name")
    return text


def apply_template(session, project_id, template_id, fields, actor):
    template = _template(template_id)
    name = str(fields.get("name") or template["title"]).strip()
    if not 1 <= len(name) <= 128:
        raise ValueError("invalid name")
    if template["type"] in ("app", "dashboard"):
        content = template["content"]
        if template["type"] == "app":
            from odf.appstudio.content import validate_app
            errors = validate_app(session, content, project_id)
        else:
            from odf.dashboards.content import validate_dashboard
            errors = validate_dashboard(session, content, project_id)
        if errors:
            raise ValueError("; ".join(item["message"] for item in errors))
        asset = create_asset(session, project_id, template["type"], name,
                             content, actor)
        return {"id": asset.id, "type": template["type"]}
    table = _table(fields.get("table"))
    if template["type"] == "model":
        datasource = _datasource(session, project_id,
                                 fields.get("datasource_id"), "query")
        schema = str(fields.get("schema_name") or "").strip()
        if schema and not _IDENT.match(schema):
            raise ValueError("invalid schema name")
        content = dict(template["content"], datasource_id=datasource.id,
                       schema=schema, description="", tests=[],
                       columns=[], partition_by=[])
        content["sql"] = content["sql"].format(table=table)
        from odf.transform.content import validate_model
        errors = validate_model(session, content, project_id)
        if errors:
            raise ValueError("; ".join(item["message"] for item in errors))
        asset = create_asset(session, project_id, "model", name, content,
                             actor)
        return {"id": asset.id, "type": "model"}
    if template["type"] == "pipeline":
        source = _datasource(session, project_id,
                             fields.get("datasource_id"), "source")
        target = _datasource(session, project_id,
                             fields.get("target_datasource_id"), "sink")
        target_table = _table(fields.get("target_table"))
        pk = str(fields.get("pk") or "id").strip()
        if not _IDENT.match(pk):
            raise ValueError("invalid primary key")
        content = {
            "nodes": [
                {"id": "source_1", "type": "source",
                 "name": "Source", "position": {"x": 80, "y": 120},
                 "config": {"datasource_id": source.id, "table": table,
                            "pk": pk}},
                {"id": "sink_1", "type": "sink", "name": "Sink",
                 "position": {"x": 430, "y": 120},
                 "config": {"datasource_id": target.id,
                            "table": target_table,
                            "mode": template["content"]["mode"],
                            "pk": [pk]}},
            ],
            "edges": [{"id": "e1", "from": "source_1", "to": "sink_1"}],
            "settings": {"batch": 1000},
        }
        from odf.pipeline.validate import validate_pipeline_content
        errors = validate_pipeline_content(session, content, project_id)
        if errors:
            raise ValueError("; ".join(item["message"] for item in errors))
        asset = create_asset(session, project_id, "pipeline", name, content,
                             actor)
        return {"id": asset.id, "type": "pipeline"}
    raise ValueError("unsupported template type")
