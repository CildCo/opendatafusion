def pipeline_content(shop_ds: int, mart_ds: int, source_table: str,
                     sink_table: str, cursor: str = "id") -> dict:
    return {
        "nodes": [
            {"id": "src", "type": "source",
             "config": {"datasource_id": shop_ds, "table": source_table,
                        "pk": "id", "cursor_column": cursor}},
            {"id": "dst", "type": "sink",
             "config": {"datasource_id": mart_ds, "table": sink_table,
                        "pk": ["id"], "mode": "upsert"}}],
        "edges": [{"from": "src", "to": "dst"}],
        "settings": {"batch": 200000},
    }


def join_pipeline(shop_ds: int, mart_ds: int) -> dict:
    return {
        "nodes": [
            {"id": "left", "type": "source",
             "config": {"datasource_id": shop_ds, "table": "order_items",
                        "pk": "id", "cursor_column": "id"}},
            {"id": "right", "type": "source",
             "config": {"datasource_id": shop_ds, "table": "products",
                        "pk": "id"}},
            {"id": "join", "type": "join",
             "config": {"left_key": "product_id", "right_key": "id",
                        "how": "left"}},
            {"id": "dst", "type": "sink",
             "config": {"datasource_id": mart_ds,
                        "table": "order_items_wide", "pk": ["id"],
                        "mode": "upsert"}}],
        "edges": [{"from": "left", "to": "join", "port": "left"},
                  {"from": "right", "to": "join", "port": "right"},
                  {"from": "join", "to": "dst"}],
        "settings": {"batch": 200000},
    }


def dataset_content(ds: int, table: str, columns: list[str],
                    limit: int = 10000) -> dict:
    return {"mode": "visual",
            "query": {"datasource_id": ds, "table": table,
                      "select": [{"column": c} for c in columns],
                      "limit": limit},
            "params": [], "sql": None, "auth": None}


def metric_content(dataset_id: int, measure_column: str = "*",
                   dimensions: list[str] | None = None) -> dict:
    return {"dataset_id": dataset_id,
            "measure": {"agg": "count" if measure_column == "*" else "sum",
                        "column": measure_column, "as": "value"},
            "dimensions": dimensions or [], "filters": [],
            "format": {"type": "number"}}


def dashboard_content(metric_ids: list[int],
                      dataset_ids: list[int]) -> dict:
    widgets = []
    for i, metric_id in enumerate(metric_ids):
        widgets.append({"id": f"m{i}", "type": "card", "metric_id": metric_id,
                        "x": (i % 4) * 3, "y": 0, "w": 3, "h": 2})
    for i, dataset_id in enumerate(dataset_ids):
        widgets.append({"id": f"t{i}", "type": "table", "dataset_id": dataset_id,
                        "x": 0, "y": 2 + i * 2, "w": 12, "h": 2})
    if not widgets:
        widgets.append({"id": "note", "type": "text", "text": "benchmark",
                        "x": 0, "y": 0, "w": 3, "h": 2})
    return {"columns": 12, "row_height": 80, "widgets": widgets}


def app_content(dataset_id: int, metric_id: int) -> dict:
    return {"start_page": "p1", "pages": [{
        "id": "p1", "title": "经营概览", "params": [],
        "components": [
            {"id": "m", "type": "metric", "metric_id": metric_id},
            {"id": "t", "type": "table", "dataset_id": dataset_id,
             "limit": 50}]}]}


def api_content(ds: int, table: str) -> dict:
    return {"mode": "visual",
            "query": {"datasource_id": ds, "table": table,
                      "select": [{"column": "id"}], "limit": 100},
            "params": [], "sql": None,
            "auth": {"type": "aksk", "rate_limit_per_min": 600}}


def quality_rule(dataset_id: int, column: str) -> dict:
    return {"dataset_id": dataset_id, "name": f"{column} range",
            "kind": "range", "column_name": column,
            "config": {"min": 0, "max": 1000000}}
