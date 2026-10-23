from datetime import datetime, timedelta, timezone

from odf.services.health import compute_health, cron_period_seconds


def test_lag_critical():
    now = datetime.now(timezone.utc)
    runs = [type("R", (), {
        "status": 2,
        "started_at": now - timedelta(hours=2),
        "in_num": 10,
        "cursor_value": "x",
    })()]
    h = compute_health(runs, now, 300)
    assert h["status"] == "critical"


def test_naive_started_at_is_treated_as_utc():
    now = datetime.now(timezone.utc)
    runs = [type("R", (), {
        "status": 2,
        "started_at": (now - timedelta(hours=2)).replace(tzinfo=None),
        "in_num": 10,
        "cursor_value": "x",
    })()]
    h = compute_health(runs, now, 300)
    assert h["status"] == "critical"


def test_period_from_cron():
    assert cron_period_seconds("0 */5 * * * ?") == 300


def test_empty_rounds_warning():
    now = datetime.now(timezone.utc)
    runs = [type("R", (), {
        "status": 2,
        "started_at": now - timedelta(seconds=60),
        "in_num": 0,
        "cursor_value": "x",
    })() for _ in range(3)]
    h = compute_health(runs, now, 300)
    assert h["status"] == "warning"
    assert h["empty_rounds"] == 3


def test_frozen_cursor_critical():
    now = datetime.now(timezone.utc)
    runs = [type("R", (), {
        "status": 2,
        "started_at": now - timedelta(hours=48),
        "in_num": 1,
        "cursor_value": "x",
    })(), type("R", (), {
        "status": 2,
        "started_at": now - timedelta(minutes=5),
        "in_num": 1,
        "cursor_value": "x",
    })()]
    h = compute_health(runs, now, 300)
    assert h["cursor_age_s"] >= 47 * 3600
    assert h["status"] == "critical"
