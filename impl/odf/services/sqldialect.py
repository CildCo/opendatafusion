def _split_order(body: str) -> tuple[str, str]:
    """Split the trailing top-level ORDER BY off a statement.

    SQL Server rejects ORDER BY inside a derived table (error 1033) and
    Oracle rejects it in an inline view, so callers wrap the statement
    without the clause and re-apply it to the outer select.
    """
    depth = 0
    quote = ""
    idx = -1
    i = 0
    low = body.lower()
    while i < len(body):
        ch = body[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and low.startswith("order by", i):
            before = body[i - 1] if i else " "
            after = body[i + 8] if i + 8 < len(body) else " "
            if not (before.isalnum() or before == "_") and not (
                    after.isalnum() or after == "_"):
                idx = i
            i += 7
        i += 1
    if idx < 0:
        return body, ""
    return body[:idx].rstrip(), body[idx:].strip()


def limited(sql: str, dialect: str, rows: int) -> str:
    body = (sql or "").strip().rstrip(";")
    dialect = (dialect or "").lower()
    if dialect == "oracle":
        prefix, order = _split_order(body)
        inner = "SELECT * FROM (%s) _odf_wb" % prefix
        if order:
            inner += " " + order
        return inner + " FETCH FIRST %d ROWS ONLY" % rows
    if dialect in ("mssql", "sqlserver"):
        prefix, order = _split_order(body)
        outer = "SELECT TOP %d * FROM (%s) AS _odf_wb" % (rows, prefix)
        if order:
            outer += " " + order
        return outer
    return "SELECT * FROM (%s) AS _odf_wb LIMIT %d" % (body, rows)
