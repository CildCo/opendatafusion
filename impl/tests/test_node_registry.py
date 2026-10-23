from odf.pipeline.nodes.base import (Column, NodeExecutor, get_node,
                                     register_node)


def test_register_and_lookup():
    @register_node("dummy")
    class Dummy(NodeExecutor):
        def schema(self, inputs, config):
            return [Column("x", "int")]

        def run(self, inputs, config, ctx):
            return inputs[0]

    assert get_node("dummy").__name__ == "Dummy"
