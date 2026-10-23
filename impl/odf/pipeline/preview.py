from odf.pipeline.runner import execute_pipeline


def preview_pipeline(session, asset_id, node_id, limit=100, content=None):
    limit = max(1, min(int(limit), 1000))
    result = execute_pipeline(session, asset_id, preview=True,
                              target_node=node_id, limit=limit,
                              content_override=content)
    return {"node_id": node_id, "rows": result["rows"],
            "node_stats": result["node_stats"]}
