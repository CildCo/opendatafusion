from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Column, Dataset, Datasource
from odf.services.crypto import encrypt_secret
from odf.services.quality import create_rule, list_results, run_rule


def _setup(tmp_path):
    db = tmp_path / "q.db"
    url = "sqlite:///" + str(db)
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int primary key, v text)"))
        c.execute(text("insert into t values (1, 'a')"))
        c.execute(text("insert into t values (2, null)"))
        c.execute(text("insert into t values (3, 'a')"))

    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.add(Dataset(id=1, datasource_id=1, schema_name="main", table_name="t"))
    s.add(Column(id=1, dataset_id=1, name="v", data_type="TEXT"))
    s.commit()
    return s


def test_not_null_fails(tmp_path):
    s = _setup(tmp_path)
    rule = create_rule(s, 1, 1, "v not null", "not_null", "v")
    result = run_rule(s, rule.id)
    assert result.status == "fail"
    assert result.detail_json["nulls"] == 1
    assert list_results(s, rule.id)


def test_unique_fails(tmp_path):
    s = _setup(tmp_path)
    rule = create_rule(s, 1, 1, "v unique", "unique", "v")
    assert run_rule(s, rule.id).status == "fail"


def test_row_count_passes(tmp_path):
    s = _setup(tmp_path)
    rule = create_rule(s, 1, 1, "3 rows", "row_count",
                       config={"min": 3, "max": 3})
    assert run_rule(s, rule.id).status == "pass"


def test_duckdb_quality_uses_query_layer(tmp_path):
    import duckdb

    path = tmp_path / "q.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create table t (id integer, v varchar)")
    con.execute("insert into t values (1, 'a'), (2, null)")
    con.close()

    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    dsn = "duckdb:///" + path.as_posix()
    s.add(Datasource(id=2, project_id=1, name="duck", kind="duckdb",
                     dsn_encrypted=encrypt_secret(dsn)))
    s.add(Dataset(id=2, datasource_id=2, schema_name="main", table_name="t"))
    s.add(Column(id=2, dataset_id=2, name="v", data_type="VARCHAR"))
    s.commit()
    rule = create_rule(s, 1, 2, "duck v not null", "not_null", "v")
    result = run_rule(s, rule.id)
    assert result.status == "fail"
    assert result.detail_json["nulls"] == 1
