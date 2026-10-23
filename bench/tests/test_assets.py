from bench.seed import assets


def test_pipeline_shape():
    content = assets.pipeline_content(1, 2, "orders", "orders_clean", "id")
    assert [n["type"] for n in content["nodes"]] == ["source", "sink"]
    assert content["edges"] == [{"from": "src", "to": "dst"}]
    assert content["nodes"][0]["config"]["cursor_column"] == "id"


def test_model_contents():
    ds = assets.dataset_content(1, "orders", ["id", "amount"], 500)
    assert ds["query"]["limit"] == 500
    metric = assets.metric_content(10, "amount", ["province"])
    assert metric["dimensions"] == ["province"]
    dash = assets.dashboard_content([11], [10])
    assert dash["widgets"]
    app = assets.app_content(10, 11)
    assert app["pages"][0]["components"]
    api = assets.api_content(1, "orders")
    assert api["auth"]["type"] == "aksk"
    rule = assets.quality_rule(10, "amount")
    assert rule["kind"] == "range"
