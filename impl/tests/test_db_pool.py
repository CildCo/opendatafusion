from types import SimpleNamespace

from odf.db import _pool_kwargs


def test_pool_kwargs_skip_sqlite_and_apply_to_postgres():
    s = SimpleNamespace(db_pool_size=10, db_max_overflow=20,
                        db_pool_timeout=30, db_pool_recycle_s=1800)
    assert _pool_kwargs("sqlite:///x.db", s) == {}
    out = _pool_kwargs("postgresql+psycopg://u@h/db", s)
    assert out["pool_size"] == 10
    assert out["max_overflow"] == 20
    assert out["pool_timeout"] == 30
    assert out["pool_recycle"] == 1800
    assert out["pool_use_lifo"] is True
