def envelope(items, total: int, page: int, page_size: int):
    return {"items": items, "total": int(total), "page": int(page),
            "page_size": int(page_size)}


def limits(page=1, page_size=50, max_size=200):
    try:
        page = max(1, int(page or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = max(1, min(int(page_size or 50), max_size))
    except (TypeError, ValueError):
        page_size = 50
    return page, page_size
