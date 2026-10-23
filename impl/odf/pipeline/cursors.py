from odf.models import AssetVersion


def _content(session, asset):
    vid = asset.published_version_id or asset.draft_version_id
    version = session.get(AssetVersion, vid) if vid else None
    if not version:
        raise ValueError("pipeline content not found")
    return version.content_json or {}


def _sources(content):
    return [n for n in content.get("nodes") or []
            if isinstance(n, dict) and n.get("type") == "source"]


def list_cursors(session, asset):
    content = _content(session, asset)
    cursors = dict(asset.cursor_json or {})
    sources = []
    for node in _sources(content):
        config = node.get("config") or {}
        sources.append({"node_id": node["id"],
                        "table": config.get("table"),
                        "cursor_column": config.get("cursor_column"),
                        "cursor": cursors.get(node["id"])})
    return {"cursors": cursors, "sources": sources}


def set_cursor(session, asset, node_id: str, cursor):
    if cursor is not None:
        if not isinstance(cursor, str) or not cursor.strip():
            raise ValueError("cursor must be a non-empty string or null")
        cursor = cursor.strip()
    content = _content(session, asset)
    node = next((n for n in _sources(content) if n.get("id") == node_id),
                None)
    if not node:
        raise ValueError("source node not found: %s" % node_id)
    cursors = dict(asset.cursor_json or {})
    if cursor is None:
        cursors.pop(node_id, None)
    else:
        cursors[node_id] = cursor
    asset.cursor_json = cursors
    session.commit()
    session.refresh(asset)
    return list_cursors(session, asset)
