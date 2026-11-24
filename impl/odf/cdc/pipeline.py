import re

from odf.assets.service import create_asset
from odf.connectors.registry import supports
from odf.models import Datasource
from odf.pipeline.validate import validate_pipeline_content

MAX_TABLES = 10
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")


def _datasource(session, project_id, datasource_id, capability):
    datasource = session.get(Datasource, datasource_id) \
        if isinstance(datasource_id, int) else None
    if not datasource or datasource.project_id != project_id:
        raise ValueError("datasource not found")
    if not supports(datasource.kind, capability):
        raise ValueError("%s is not a %s datasource"
                         % (datasource.kind, capability))
    return datasource


def subscribed_tables(source):
    raw = str((source.config_json or {}).get("table_list") or "")
    tables = [item.strip() for item in raw.split(",") if item.strip()]
    for table in tables:
        if not _TABLE.match(table):
            raise ValueError("invalid table name: %s" % table)
    return tables


def topic_for(source, table):
    prefix = str((source.config_json or {}).get("topic_prefix") or "odf")
    return "%s.%s" % (prefix, table)


def build_pipeline(session, project_id, source, kafka_datasource_id,
                   sink_datasource_id, sink_table="", name="", actor="",
                   pk="id"):
    if source is None or source.project_id != project_id:
        raise ValueError("cdc source not found")
    kafka = _datasource(session, project_id, kafka_datasource_id, "source")
    if kafka.kind != "kafka":
        raise ValueError("the CDC stream requires a Kafka datasource")
    sink = _datasource(session, project_id, sink_datasource_id, "sink")
    if not isinstance(pk, str) or not _IDENT.match(pk):
        raise ValueError("invalid primary key column")
    tables = subscribed_tables(source)
    if not tables:
        raise ValueError("the CDC source has no subscribed tables")
    if len(tables) > MAX_TABLES:
        raise ValueError("at most %d tables per generated pipeline"
                         % MAX_TABLES)
    sink_table = (sink_table or "").strip()
    if sink_table and not _TABLE.match(sink_table):
        raise ValueError("invalid target table")
    nodes, edges = [], []
    for index, table in enumerate(tables, 1):
        target = sink_table.split(".")[-1] \
            if sink_table and len(tables) == 1 else table.split(".")[-1]
        source_id, sink_id = "cdc_%d" % index, "sink_%d" % index
        y = 80 + (index - 1) * 150
        nodes.append({
            "id": source_id, "type": "source", "name": "CDC " + table,
            "position": {"x": 80, "y": y},
            "config": {"datasource_id": kafka.id,
                       "table": topic_for(source, table), "pk": pk,
                       "debezium": True, "cdc_delete": True}})
        nodes.append({
            "id": sink_id, "type": "sink", "name": "Sink " + target,
            "position": {"x": 430, "y": y},
            "config": {"datasource_id": sink.id, "table": target,
                       "mode": "cdc", "pk": [pk]}})
        edges.append({"id": "e%d" % index, "from": source_id,
                      "to": sink_id})
    content = {"nodes": nodes, "edges": edges,
               "settings": {"batch": 1000}}
    errors = validate_pipeline_content(session, content, project_id)
    if errors:
        raise ValueError("; ".join(
            "%s: %s" % (item.get("field") or "pipeline", item["message"])
            for item in errors[:5]))
    title = (name or "").strip() or "CDC %s" % source.name
    asset = create_asset(session, project_id, "pipeline", title, content,
                         actor or "system")
    return {"id": asset.id, "name": asset.name, "topics":
            [topic_for(source, table) for table in tables]}
