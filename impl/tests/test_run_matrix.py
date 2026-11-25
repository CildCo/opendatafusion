from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Job, Project
from odf.ops.service import run_matrix


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.commit()
    return s


def test_run_matrix_groups_assets_and_days():
    s = _env()
    one = create_asset(s, 1, "pipeline", "alpha", {"nodes": [], "edges": []},
                       "admin")
    two = create_asset(s, 1, "pipeline", "beta", {"nodes": [], "edges": []},
                       "admin")
    now = datetime.now(timezone.utc)
    s.add_all([
        Job(project_id=1, asset_id=one.id, asset_type="pipeline",
            status="success", created_at=now),
        Job(project_id=1, asset_id=one.id, asset_type="pipeline",
            status="failed", created_at=now),
        Job(project_id=1, asset_id=two.id, asset_type="pipeline",
            status="success", created_at=now - timedelta(days=1)),
    ])
    s.commit()
    out = run_matrix(s, 1, 7)
    assert len(out["days"]) == 7
    rows = {row["name"]: row for row in out["rows"]}
    assert rows["alpha"]["total"] == 2
    today = now.date().isoformat()
    assert rows["alpha"]["cells"][today]["status"] == "failed"
    assert rows["alpha"]["cells"][today]["count"] == 2
    yesterday = (now - timedelta(days=1)).date().isoformat()
    assert rows["beta"]["cells"][yesterday]["status"] == "success"


def test_run_matrix_limits_days():
    s = _env()
    assert len(run_matrix(s, 1, 99)["days"]) == 30
    assert len(run_matrix(s, 1, 0)["days"]) == 1
