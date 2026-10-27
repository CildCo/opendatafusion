import pytest

from odf.models import Alert, Column, Dataset, Datasource
from odf.services.crypto import encrypt_secret
from odf.services.metadata import sync_datasource


class _FakeClient:
    catalog = "iceberg"

    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def query(self, sql, max_rows=1000):
        self.statements.append(sql)
        return {"columns": ["table_schema", "table_name", "column_name",
                            "data_type"],
                "rows": self.rows, "row_count": len(self.rows),
                "truncated": False}


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _ds(session, name):
    ds = Datasource(project_id=1, name=name, kind="trino",
                    dsn_encrypted=encrypt_secret(
                        "trino://odf@trino:8080/iceberg/demo"))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


def _rows(table, columns, schema="demo"):
    return [{"table_schema": schema, "table_name": table,
             "column_name": name, "data_type": kind}
            for name, kind in columns]


def test_sync_trino_writes_datasets_and_columns(session, monkeypatch):
    fake = _FakeClient(_rows("events", [("id", "bigint"),
                                        ("name", "varchar")])
                       + _rows("orders", [("id", "bigint")]))
    monkeypatch.setattr("odf.services.metadata.client_for_datasource",
                        lambda ds: fake)
    ds = _ds(session, "lake-sync")

    count = sync_datasource(session, ds.id)

    assert count == 2
    assert "iceberg.information_schema.columns" in fake.statements[0]
    events = (session.query(Dataset)
              .filter_by(datasource_id=ds.id, table_name="events").one())
    cols = session.query(Column).filter_by(dataset_id=events.id).all()
    assert {c.name: c.data_type for c in cols} == {"id": "bigint",
                                                   "name": "varchar"}


def test_sync_trino_replaces_previous_metadata(session, monkeypatch):
    ds = _ds(session, "lake-replace")
    monkeypatch.setattr(
        "odf.services.metadata.client_for_datasource",
        lambda d: _FakeClient(_rows("events", [("id", "bigint")])))
    sync_datasource(session, ds.id)

    monkeypatch.setattr(
        "odf.services.metadata.client_for_datasource",
        lambda d: _FakeClient(_rows("events", [("id", "bigint"),
                                               ("ts", "timestamp")])))
    sync_datasource(session, ds.id)

    rows = (session.query(Dataset).filter_by(datasource_id=ds.id).all())
    assert len(rows) == 1
    cols = session.query(Column).filter_by(dataset_id=rows[0].id).all()
    assert {c.name for c in cols} == {"id", "ts"}


def test_sync_trino_raises_schema_drift_alert(session, monkeypatch):
    ds = _ds(session, "lake-drift")
    session.query(Alert).filter_by(
        project_id=1, title="schema drift: demo.events").delete()
    session.commit()
    monkeypatch.setattr(
        "odf.services.metadata.client_for_datasource",
        lambda d: _FakeClient(_rows("events", [("id", "bigint")])))
    sync_datasource(session, ds.id)
    monkeypatch.setattr(
        "odf.services.metadata.client_for_datasource",
        lambda d: _FakeClient(_rows("events", [("id", "varchar")])))
    sync_datasource(session, ds.id)

    alert = (session.query(Alert)
             .filter_by(project_id=1, title="schema drift: demo.events").one())
    assert alert.severity == "warning"
    assert alert.detail_json["type_changed"] == [
        {"column": "id", "from": "bigint", "to": "varchar"}]


def test_sync_trino_requires_catalog(session, monkeypatch):
    ds = _ds(session, "lake-nocat")
    fake = _FakeClient([])
    fake.catalog = ""
    monkeypatch.setattr("odf.services.metadata.client_for_datasource",
                        lambda d: fake)
    with pytest.raises(ValueError, match="catalog"):
        sync_datasource(session, ds.id)
