from types import SimpleNamespace

from odf.apistudio.catalog import table_column_info
from odf.models import Asset, AssetVersion, Datasource
from odf.pipeline.nodes import sink as _sink  # noqa: F401
from odf.pipeline.nodes import source as _source  # noqa: F401
from odf.pipeline.nodes import transform as _transform  # noqa: F401
from odf.pipeline.nodes.base import Column, get_node
from odf.pipeline.schema import input_edges, topo_order, validate_dag


def content_schemas(session, content, project_id=0):
    errs = validate_dag(content)
    if errs:
        raise ValueError("invalid dag: %s" % errs)
    nodes = {n["id"]: n for n in content["nodes"]}
    schemas, out = {}, []
    for nid in topo_order(content):
        node = nodes[nid]
        config = node.get("config") or {}
        if node["type"] == "source":
            ds_id = config.get("datasource_id")
            ds = session.get(Datasource, ds_id) if ds_id else None
            if not ds:
                raise ValueError("datasource not found for node %s" % nid)
            if project_id and ds.project_id != project_id:
                raise ValueError("datasource for node %s is outside the project"
                                 % nid)
            info = table_column_info(session, ds, config.get("table"))
            schema = [Column(c["name"], c["type"]) for c in info]
        else:
            edges = input_edges(content, nid)
            inputs = [schemas[e["from"]] for e in edges
                      if e["from"] in schemas]
            if len(inputs) != len(edges):
                raise ValueError("node %s has unresolved inputs" % nid)
            if node["type"] == "sink":
                ds_id = config.get("datasource_id")
                ds = session.get(Datasource, ds_id) if ds_id else None
                if not ds:
                    raise ValueError("datasource not found for node %s" % nid)
                if project_id and ds.project_id != project_id:
                    raise ValueError(
                        "datasource for node %s is outside the project" % nid)
                target = {c["name"] for c in table_column_info(
                    session, ds, config.get("table"))}
                schema = inputs[0].schema if inputs else []
                missing = [c.name for c in schema if c.name not in target]
                if missing:
                    raise ValueError("node %s sink missing target columns: %s"
                                     % (nid, ", ".join(missing)))
            else:
                try:
                    schema = get_node(node["type"])().schema(inputs, config)
                except Exception as e:
                    raise ValueError("node %s: %s" % (nid, e))
        schemas[nid] = SimpleNamespace(schema=schema)
        out.append({"node_id": nid, "type": node["type"],
                    "columns": [{"name": c.name, "type": c.type}
                                for c in schema]})
    return out


def node_schemas(session, asset_id, published=True):
    a = session.get(Asset, asset_id)
    if not a or a.type != "pipeline":
        raise ValueError("pipeline not found")
    vid = a.published_version_id if published else a.draft_version_id
    if not vid:
        vid = a.published_version_id or a.draft_version_id
    used = "published" if (a.published_version_id
                           and vid == a.published_version_id) else "draft"
    v = session.get(AssetVersion, vid) if vid else None
    if not v:
        raise ValueError("content not found")
    nodes = content_schemas(session, v.content_json, a.project_id)
    return {"asset_id": asset_id, "version": v.version,
            "published": used == "published", "source": used,
            "nodes": nodes}
