from odf.services.sqldialect import limited


def test_limit_syntax_per_dialect():
    assert limited("select * from t;", "oracle", 10) == (
        "SELECT * FROM (select * from t) odf_wb FETCH FIRST 10 ROWS ONLY")
    assert limited("select * from t", "mssql", 5) == (
        "SELECT TOP 5 * FROM (select * from t) AS _odf_wb")
    assert limited("select * from t", "postgresql", 5) == (
        "SELECT * FROM (select * from t) AS _odf_wb LIMIT 5")


def test_limit_keeps_order_by_outside_the_derived_table():
    # ORDER BY inside a derived table is rejected by SQL Server (1033) and
    # Oracle, so the wrapper has to lift the outer ORDER BY.
    assert limited("select id from t order by id", "mssql", 5) == (
        "SELECT TOP 5 * FROM (select id from t) AS _odf_wb order by id")
    assert limited("select id from t ORDER BY id", "oracle", 5) == (
        "SELECT * FROM (select id from t) odf_wb ORDER BY id "
        "FETCH FIRST 5 ROWS ONLY")


def test_limit_ignores_order_by_inside_subqueries_and_strings():
    assert limited("select * from (select id from t) x order by id",
                   "mssql", 5) == (
        "SELECT TOP 5 * FROM (select * from (select id from t) x) "
        "AS _odf_wb order by id")
    assert limited("select 'order by' as s from t order by s",
                   "mssql", 5) == (
        "SELECT TOP 5 * FROM (select 'order by' as s from t) "
        "AS _odf_wb order by s")
