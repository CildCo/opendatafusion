import pytest

from odf.apistudio.sqlguard import SqlGuardError, ensure_read_only


def test_select_and_with_are_allowed():
    ensure_read_only("select * from t where id = :id")
    ensure_read_only("WITH x AS (select 1) SELECT * FROM x")


def test_dml_and_ddl_are_rejected():
    for sql in ["delete from t", "update t set a=1",
                "insert into t values (1)", "drop table t",
                "alter table t add column a int", "truncate t"]:
        with pytest.raises(SqlGuardError):
            ensure_read_only(sql)


def test_multiple_statements_are_rejected():
    with pytest.raises(SqlGuardError):
        ensure_read_only("select 1; delete from t")


def test_comments_are_ignored_before_the_first_keyword():
    ensure_read_only("-- comment\n/* block */ select 1")


def test_nested_block_comments_are_rejected():
    with pytest.raises(SqlGuardError):
        ensure_read_only("/* a /* b */ select 1")


def test_forbidden_word_inside_identifier_is_allowed():
    ensure_read_only('select "update_count" from t')


def test_dash_inside_string_does_not_hide_statement():
    with pytest.raises(SqlGuardError):
        ensure_read_only("select '--' ; drop table t")


def test_dollar_quoted_payload_does_not_hide_statement():
    with pytest.raises(SqlGuardError):
        ensure_read_only("select $$x$$; delete from t")


def test_quoted_identifier_and_literal_are_allowed():
    ensure_read_only('select "delete" from t where x = \'update\'')


def test_read_side_effect_constructs_are_rejected():
    import pytest
    from odf.apistudio.sqlguard import SqlGuardError, ensure_read_only
    for sql in (
            "select * from t into outfile '/tmp/x'",
            "select load_file('/etc/passwd')",
            "select * from t for update",
            "select nextval('seq')"):
        with pytest.raises(SqlGuardError):
            ensure_read_only(sql)
