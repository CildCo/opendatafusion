import pytest

from odf.apistudio.compiler import (CompileError, compile_visual, quote_ident,
                                    render_sql)

COLS = ["city", "amount", "created_at", "status"]


def test_compile_select_filter_group_order_limit():
    query = {
        "datasource_id": 1,
        "table": "public.orders",
        "select": [{"column": "city"},
                   {"column": "amount", "agg": "sum", "as": "total"}],
        "filters": [
            {"column": "status", "op": "=", "value": "paid"},
            {"column": "created_at", "op": ">=", "param": "start"},
        ],
        "group_by": ["city"],
        "order_by": [{"column": "total", "dir": "desc"}],
        "limit": 500,
    }
    sql, binds = compile_visual(query, COLS, {"start": "2026-01-01"})
    assert sql == (
        'SELECT "city", SUM("amount") AS "total" FROM "public"."orders" '
        'WHERE "status" = :status AND "created_at" >= :start '
        'GROUP BY "city" ORDER BY "total" DESC LIMIT 500')
    assert binds == {"status": "paid", "start": "2026-01-01"}


def test_compile_rejects_unknown_column_and_injection():
    with pytest.raises(CompileError):
        compile_visual({"datasource_id": 1, "table": "t",
                        "select": [{"column": "nope"}]}, COLS, {})
    payload = 'city" FROM read_csv_auto(\'C:/secret.csv\') --'
    with pytest.raises(CompileError):
        compile_visual({"datasource_id": 1, "table": "t",
                        "select": [{"column": payload}]}, COLS, {})


def test_compile_rejects_bad_alias():
    with pytest.raises(CompileError):
        compile_visual({"datasource_id": 1, "table": "t",
                        "select": [{"column": "city", "as": 'x" --'}]},
                       COLS, {})


def test_in_filter_expands_and_binds():
    query = {"datasource_id": 1, "table": "t",
             "select": [{"column": "city"}],
             "filters": [{"column": "status", "op": "in",
                          "value": ["paid", "new"]}]}
    sql, binds = compile_visual(query, COLS, {})
    assert sql == ('SELECT "city" FROM "t" WHERE "status" IN '
                   '(:status_0, :status_1) LIMIT 1000')
    assert binds == {"status_0": "paid", "status_1": "new"}


def test_is_null_has_no_bind():
    query = {"datasource_id": 1, "table": "t",
             "select": [{"column": "city"}],
             "filters": [{"column": "status", "op": "is null"}]}
    sql, binds = compile_visual(query, COLS, {})
    assert sql == 'SELECT "city" FROM "t" WHERE "status" IS NULL LIMIT 1000'
    assert binds == {}


def test_limit_is_clamped():
    query = {"datasource_id": 1, "table": "t",
             "select": [{"column": "city"}], "limit": 999999}
    sql, _ = compile_visual(query, COLS, {})
    assert sql.endswith("LIMIT 10000")


def test_group_by_must_be_selected():
    query = {"datasource_id": 1, "table": "t",
             "select": [{"column": "amount", "agg": "sum"}],
             "group_by": ["city"]}
    with pytest.raises(CompileError):
        compile_visual(query, COLS, {})


def test_render_sql_rejects_undeclared_placeholder():
    with pytest.raises(CompileError):
        render_sql("select * from t where id = ${missing}",
                   [{"name": "id", "type": "number"}], {"id": 1})


def test_render_sql_binds_declared_placeholder():
    sql, binds = render_sql(
        "select * from t where id = ${id} and day = ${day}",
        [{"name": "id", "type": "number"}, {"name": "day", "type": "date"}],
        {"id": 2, "day": "2026-01-01"})
    assert sql == "select * from t where id = :id and day = :day"
    assert binds == {"id": 2, "day": "2026-01-01"}


def test_quote_ident_doubles_quotes():
    assert quote_ident('a"b') == '"a""b"'


def test_column_name_is_not_used_as_bind_key():
    cols = ["id OR 1=1 --"]
    sql, binds = compile_visual(
        {"table": "t", "select": [{"column": cols[0]}],
         "filters": [{"column": cols[0], "op": "=", "value": 1}]}, cols, {})
    assert binds == {"id_OR_1_1___": 1}
    assert ":id OR" not in sql


def test_two_filters_on_same_column_use_distinct_binds():
    sql, binds = compile_visual(
        {"table": "t", "select": [{"column": "amount"}],
         "filters": [{"column": "amount", "op": ">", "value": 10},
                     {"column": "amount", "op": "<", "value": 20}]},
        ["amount"], {})
    assert binds == {"amount": 10, "amount_1": 20}
    assert ":amount" in sql and ":amount_1" in sql


def test_blank_optional_param_skips_filter():
    query = {"datasource_id": 1, "table": "t",
             "select": [{"column": "city"}],
             "filters": [{"column": "status", "op": "=", "param": "status"}]}
    sql, binds = compile_visual(query, COLS, {"status": ""})
    assert sql == 'SELECT "city" FROM "t" LIMIT 1000'
    assert binds == {}


def test_literal_in_list_is_capped():
    query = {"datasource_id": 1, "table": "t",
             "select": [{"column": "city"}],
             "filters": [{"column": "status", "op": "in",
                          "value": [str(i) for i in range(101)]}]}
    with pytest.raises(CompileError):
        compile_visual(query, COLS, {})
