from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.services.alerts import (ack_alert, close_alert, evaluate_health,
                                 list_alerts, raise_alert)


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_alert_dedupe_and_lifecycle():
    s = _session()
    a = raise_alert(s, 1, "critical", "flow x: critical", {"flow_id": 1})
    b = raise_alert(s, 1, "critical", "flow x: critical", {"flow_id": 1})
    assert a.id == b.id
    assert len(list_alerts(s, 1, "open")) == 1
    assert ack_alert(s, a.id).status == "acked"
    assert close_alert(s, a.id).status == "closed"


def test_evaluate_health_creates_alert():
    s = _session()
    a = evaluate_health(s, 1, 2, "copy", {"status": "critical", "lag_s": 999})
    assert a is not None
    assert a.severity == "critical"
    assert list_alerts(s, 1, "open")[0].title == "flow copy: critical"


def test_evaluate_health_ignores_ok():
    s = _session()
    assert evaluate_health(s, 1, 2, "copy", {"status": "ok"}) is None
