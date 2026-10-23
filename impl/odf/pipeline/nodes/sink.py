from odf.connectors.factory import sink_for
from odf.models import Datasource
from odf.pipeline.nodes.base import NodeExecutor, register_node


@register_node("sink")
class SinkExecutor(NodeExecutor):
    def schema(self, inputs, config):
        return []

    def run(self, inputs, config, ctx):
        table = inputs[0]
        if ctx.preview:
            return table
        ds = ctx.session.get(Datasource, config["datasource_id"])
        pks = config.get("pk") or ["id"]
        if not isinstance(pks, list):
            pks = [pks]
        dag = {"sink_table": config["table"], "pk": pks,
               "mode": config.get("mode") or "upsert"}
        sink_for(ds, dag).write(table.to_pylist())
        return table
