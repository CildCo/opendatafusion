from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Flow, FlowRun


def test_dashboard_counts_running_and_failed():
    from odf.api.dashboard import dashboard
    from types import SimpleNamespace
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Flow(id=1, project_id=1, name="f", status=1))
    now = datetime.now(timezone.utc)
    s.add_all([
        FlowRun(flow_id=1, status=1, started_at=now),
        FlowRun(flow_id=1, status=3, started_at=now),
        FlowRun(flow_id=1, status=2, started_at=now),
        FlowRun(flow_id=1, status=3,
                started_at=now - timedelta(days=2)),
    ])
    s.commit()
    out = dashboard(s, SimpleNamespace(project_id=1))
    assert out["running_runs"] == 1
    assert out["failed_24h"] == 1
    assert out["runs_24h"] == 3
