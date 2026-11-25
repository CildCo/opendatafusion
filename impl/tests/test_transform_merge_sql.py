from odf.transform.service import merge_sql


def test_merge_sql_includes_update_and_insert():
    sql = merge_sql('"cat"."s"."t"', "select city, total from orders",
                    ["city"], ["city", "total"])
    assert sql.startswith('MERGE INTO "cat"."s"."t" t USING')
    assert 'ON (t."city" = s."city")' in sql
    assert 'WHEN MATCHED THEN UPDATE SET "total" = s."total"' in sql
    assert 'WHEN NOT MATCHED THEN INSERT ("city", "total")' in sql
    assert 'VALUES (s."city", s."total")' in sql


def test_merge_sql_with_only_key_columns_skips_update():
    sql = merge_sql('"t"', "select id from t", ["id"], ["id"])
    assert "WHEN MATCHED" not in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql
