import ipaddress
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from odf.models import ApiCallStat, ApiRate, Asset


def client_allowed(ip, allowlist):
    if not allowlist:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for item in allowlist:
        try:
            if addr in ipaddress.ip_network(item, strict=False):
                return True
        except ValueError:
            continue
    return False


def _window(now):
    now = now or datetime.now(timezone.utc)
    return now.replace(second=0, microsecond=0)


def check_rate(session, key, limit, now=None):
    if not limit or limit <= 0:
        return True
    window = _window(now)
    for _ in range(2):
        row = session.get(ApiRate, key)
        if not row:
            session.add(ApiRate(key=key, window_start=window, count=1))
            try:
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                continue
        start = row.window_start
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start < window:
            row.window_start = window
            row.count = 1
            session.commit()
            return True
        if row.count >= limit:
            return False
        row.count += 1
        session.commit()
        return True
    return True


def record_stat(session, day, api_id, ak, ok, ms):
    for _ in range(2):
        row = (session.query(ApiCallStat)
               .filter_by(day=day, api_id=api_id, ak=ak).first())
        if row:
            row.count += 1
            if not ok:
                row.errors += 1
            row.total_ms += int(ms)
            session.commit()
            return
        session.add(ApiCallStat(day=day, api_id=api_id, ak=ak, count=1,
                                errors=0 if ok else 1,
                                total_ms=int(ms)))
        try:
            session.commit()
            return
        except IntegrityError:
            session.rollback()
    return


def stats(session, project_id, days=7):
    since = datetime.now(timezone.utc).date()
    from datetime import timedelta
    since = since - timedelta(days=max(1, days) - 1)
    rows = (session.query(ApiCallStat.api_id, ApiCallStat.ak,
                          func.sum(ApiCallStat.count),
                          func.sum(ApiCallStat.errors),
                          func.sum(ApiCallStat.total_ms))
            .join(Asset, Asset.id == ApiCallStat.api_id)
            .filter(Asset.project_id == project_id,
                    ApiCallStat.day >= since)
            .group_by(ApiCallStat.api_id, ApiCallStat.ak).all())
    out = []
    for api_id, ak, count, errors, total_ms in rows:
        asset = session.get(Asset, api_id)
        out.append({"api_id": api_id,
                    "api_name": asset.name if asset else "",
                    "key": asset.key if asset else "",
                    "ak": ak, "count": int(count or 0),
                    "errors": int(errors or 0),
                    "avg_ms": int((total_ms or 0) / max(1, count or 0))})
    return out
