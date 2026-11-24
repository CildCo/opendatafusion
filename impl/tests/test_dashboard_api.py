from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Asset, Job


def test_dashboard_counts_running_and_failed():
    from odf.api.dashboard import dashboard
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Asset(id=1, project_id=1, type="pipeline", key="p1", name="f",
                owner="admin"))
    now = datetime.now(timezone.utc)
    s.add_all([
        Job(asset_id=1, asset_type="pipeline", status="running",
            created_at=now),
        Job(asset_id=1, asset_type="pipeline", status="failed",
            created_at=now),
        Job(asset_id=1, asset_type="pipeline", status="success",
            created_at=now),
        Job(asset_id=1, asset_type="pipeline", status="failed",
            created_at=now - timedelta(days=2)),
    ])
    s.commit()
    out = dashboard(s, SimpleNamespace(project_id=1))
    assert out["running_runs"] == 1
    assert out["failed_24h"] == 1
    assert out["runs_24h"] == 3
    assert out["pipelines"] == 1
    assert {row["target"] for row in out["recent_runs"]} == {"f"}
