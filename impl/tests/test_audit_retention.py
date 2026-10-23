import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import AuditLog
from odf.services.audit import export_audit, prune_audit


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    old = datetime.now(timezone.utc) - timedelta(days=60)
    s.add_all([
        AuditLog(id=1, actor="a", action="old", target="x",
                 detail_json={"n": 1}, at=old),
        AuditLog(id=2, actor="b", action="new", target="y",
                 detail_json={}),
    ])
    s.commit()
    return s


def test_export_and_prune_old_audit(tmp_path):
    s = _session()
    before = datetime.now(timezone.utc) - timedelta(days=30)
    out = tmp_path / "audit.jsonl"
    assert export_audit(s, before, str(out)) == 1
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert row["action"] == "old" and row["detail"] == {"n": 1}
    assert prune_audit(s, before, batch_size=1) == 1
    assert s.query(AuditLog).count() == 1
    assert s.query(AuditLog).first().action == "new"
    assert prune_audit(s, before) == 0
