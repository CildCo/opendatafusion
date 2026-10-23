from odf.mcp.server import TOOLS


def test_model_tools_registered():
    assert "dataset_schema" in TOOLS
    assert "query_metric" in TOOLS
