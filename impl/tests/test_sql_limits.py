from odf.services.sqldialect import limited


def test_limit_syntax_per_dialect():
    assert limited("select * from t;", "oracle", 10) == (
        "SELECT * FROM (select * from t) _odf_wb FETCH FIRST 10 ROWS ONLY")
    assert limited("select * from t", "mssql", 5) == (
        "SELECT TOP 5 * FROM (select * from t) AS _odf_wb")
    assert limited("select * from t", "postgresql", 5) == (
        "SELECT * FROM (select * from t) AS _odf_wb LIMIT 5")
