from odf.apistudio.catalog import table_columns
from odf.connectors.factory import SINK_KINDS
from odf.models import Datasource
from odf.pipeline.schema import validate_dag


def _err(node_id, field, message):
    return {"node_id": node_id, "field": field, "message": message}


def validate_pipeline_content(session, content, project_id=0):
    errs = list(validate_dag(content))
    nodes = content.get("nodes") or []
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") not in (
                "source", "sink"):
            continue
        nid = node.get("id")
        config = node.get("config") or {}
        ds_id = config.get("datasource_id")
        ds = session.get(Datasource, ds_id) if ds_id else None
        if not ds:
            errs.append(_err(nid, "datasource_id", "数据源不存在"))
            continue
        if project_id and ds.project_id != project_id:
            errs.append(_err(nid, "datasource_id", "数据源不属于当前项目"))
            continue
        if node.get("type") == "sink" and ds.kind not in SINK_KINDS:
            errs.append(_err(nid, "datasource_id",
                             "sink kind %s is not supported" % ds.kind))
            continue
        table = config.get("table")
        if not table:
            errs.append(_err(nid, "table", "缺少表名"))
            continue
        try:
            table_columns(session, ds, table)
        except ValueError as e:
            errs.append(_err(nid, "table", str(e)))
            continue
        if node.get("type") == "source" and not config.get("pk"):
            errs.append(_err(nid, "pk", "source 缺少主键"))
        if node.get("type") == "sink" and not config.get("pk"):
            errs.append(_err(nid, "pk", "sink 缺少主键"))
    try:
        from odf.pipeline.schema_service import content_schemas
        content_schemas(session, content, project_id)
    except ValueError as e:
        errs.append(_err(None, "schema", str(e)))
    return errs
