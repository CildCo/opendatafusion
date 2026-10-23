from datetime import datetime, timedelta, timezone


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def cron_period_seconds(expr: str, default: int = 300) -> int:
    try:
        from odf.services.scheduler import cron_to_trigger
        t = cron_to_trigger(expr)
        now = datetime.now(timezone.utc)
        n1 = t.get_next_fire_time(None, now)
        n2 = t.get_next_fire_time(n1, n1 + timedelta(seconds=1))
        return int((n2 - n1).total_seconds())
    except Exception:
        return default


def compute_health(runs, now, period_s):
    if not runs:
        return {"status": "unknown", "lag_s": None, "empty_rounds": 0,
                "cursor_age_s": None}
    runs_sorted = sorted(runs, key=lambda r: _aware(r.started_at))
    ok_runs = [r for r in runs_sorted if r.status == 2]
    if not ok_runs:
        return {"status": "critical", "lag_s": None, "empty_rounds": 0,
                "cursor_age_s": None}

    last = ok_runs[-1]
    lag = int((_aware(now) - _aware(last.started_at)).total_seconds())

    empties = 0
    for r in reversed(ok_runs):
        if r.in_num == 0:
            empties += 1
        else:
            break

    cursor_age = None
    prev = object()
    last_change = None
    for r in runs_sorted:
        if r.cursor_value != prev:
            last_change = _aware(r.started_at)
            prev = r.cursor_value
    if last_change is not None and prev is not None:
        cursor_age = int((_aware(now) - last_change).total_seconds())

    if lag > 6 * period_s or (cursor_age is not None and cursor_age > 86400):
        status = "critical"
    elif lag > 2 * period_s or empties >= 3:
        status = "warning"
    else:
        status = "ok"
    return {"status": status, "lag_s": lag, "empty_rounds": empties,
            "cursor_age_s": cursor_age}


def evaluate_and_record(session, flow_id, health, period_s=300):
    if health["status"] == "ok":
        return
    from odf.models import HealthEvent
    now = datetime.now(timezone.utc)
    kinds = []
    if health.get("empty_rounds", 0) >= 3:
        kinds.append("empty")
    if health.get("cursor_age_s") is not None and health["cursor_age_s"] > 86400:
        kinds.append("cursor")
    kinds.append("lag")
    for kind in kinds:
        last = (session.query(HealthEvent).filter_by(flow_id=flow_id, kind=kind)
                .order_by(HealthEvent.at.desc()).first())
        if last and _aware(last.at) > now - timedelta(seconds=period_s):
            continue
        session.add(HealthEvent(flow_id=flow_id, kind=kind,
                                severity=health["status"],
                                evidence_json=health))
    session.commit()
