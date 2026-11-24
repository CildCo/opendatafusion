from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.services.alerts import (ack_alert, close_alert,
                                 list_alerts, raise_alert)


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_alert_dedupe_and_lifecycle():
    s = _session()
    a = raise_alert(s, 1, "critical", "pipeline x: critical", {"pipeline_id": 1})
    b = raise_alert(s, 1, "critical", "pipeline x: critical", {"pipeline_id": 1})
    assert a.id == b.id
    assert len(list_alerts(s, 1, "open")) == 1
    assert ack_alert(s, a.id).status == "acked"
    assert close_alert(s, a.id).status == "closed"
