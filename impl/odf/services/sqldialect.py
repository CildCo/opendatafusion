def limited(sql: str, dialect: str, rows: int) -> str:
    body = (sql or "").strip().rstrip(";")
    dialect = (dialect or "").lower()
    if dialect == "oracle":
        return ("SELECT * FROM (%s) _odf_wb FETCH FIRST %d ROWS ONLY"
                % (body, rows))
    if dialect in ("mssql", "sqlserver"):
        return "SELECT TOP %d * FROM (%s) AS _odf_wb" % (rows, body)
    return "SELECT * FROM (%s) AS _odf_wb LIMIT %d" % (body, rows)
