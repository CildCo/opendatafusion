from odf.services.interface import render_sql


def test_render_uses_bind_params():
    sql, binds = render_sql("select * from t where a = ${a}", {"a": 1})
    assert ":a" in sql and binds == {"a": 1}


def test_param_value_is_not_concatenated():
    sql, binds = render_sql("select * from t where a = ${a}",
                            {"a": "1; drop table x"})
    assert "drop table" not in sql
    assert binds["a"] == "1; drop table x"
