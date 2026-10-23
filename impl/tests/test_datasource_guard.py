import pytest

from odf.db import SessionLocal
from odf.services.datasource import create_datasource, is_control_database
from odf.settings import get_settings


def test_control_postgres_url_matches_with_driver_variants():
    control = "postgresql+psycopg://odf:test-password@127.0.0.1:5432/odf"
    assert is_control_database(
        "postgresql://odf:other@127.0.0.1:5432/odf", control=control)
    assert is_control_database(
        "postgres://odf@localhost:5432/odf", control=control)
    assert not is_control_database(
        "postgresql://odf:test-password@127.0.0.1:5432/other", control=control)
    assert not is_control_database(
        "postgresql://odf:test-password@db.example.com:5432/odf", control=control)


def test_control_sqlite_url_resolves_relative_and_absolute(tmp_path):
    control = "sqlite:///" + str(tmp_path / "odf.db")
    assert is_control_database(control, control=control)
    assert is_control_database(
        "sqlite:///" + str((tmp_path / "." / "odf.db").resolve()),
        control=control)
    assert not is_control_database(
        "sqlite:///" + str(tmp_path / "other.db"), control=control)


def test_create_datasource_rejects_the_control_database():
    control = get_settings().database_url
    with SessionLocal() as s:
        with pytest.raises(ValueError, match="control database"):
            create_datasource(s, 1, "self", control, "postgres")


def test_create_datasource_allows_a_different_database(tmp_path):
    target = "sqlite:///" + str(tmp_path / "business.db")
    with SessionLocal() as s:
        ds = create_datasource(s, 1, "business", target, "sqlite")
        assert ds.id
