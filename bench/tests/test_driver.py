from bench.load import driver


def test_percentile_and_summary():
    assert driver.percentile([1, 2, 3, 4], 50) == 2
    summary = driver.summarize([(200, 10.0), (200, 30.0), (500, 50.0)])
    assert summary["count"] == 3
    assert summary["errors"] == 1
    assert summary["p50_ms"] == 30.0


def test_scenario_request_targets_real_queries():
    from bench.load.driver import scenario_request
    method, path, payload = scenario_request(
        "dataset_preview", {"dataset": 7})
    assert (method, path, payload["limit"]) == (
        "POST", "/api/v1/datasets/7/preview", 20)
    method, path, _ = scenario_request("metric", {"metric": 8})
    assert (method, path) == ("POST", "/api/v1/metrics/8/query")
    method, path, _ = scenario_request("dashboard", {"dashboard": 9})
    assert (method, path) == ("POST", "/api/v1/dashboards/9/data")
    assert scenario_request("catalog")[:2] == (
        "GET", "/api/v1/catalog/search")


def test_summarize_groups_by_endpoint_kind():
    from bench.load.driver import summarize
    out = summarize([
        (200, 10.0, "dataset_preview"),
        (200, 30.0, "metric"),
        (200, 50.0, "metric"),
    ])
    assert out["by_kind"]["metric"]["count"] == 2
    assert out["by_kind"]["metric"]["p50_ms"] == 30.0
    assert out["by_kind"]["dataset_preview"]["count"] == 1
