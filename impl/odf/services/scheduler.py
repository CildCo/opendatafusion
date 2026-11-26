from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger


def project_timezone(session, project_id):
    from odf.models import Project
    project = session.get(Project, project_id) if project_id else None
    name = ((project.quota_json or {}).get("timezone")
            if project else None)
    if not name:
        return None
    try:
        return ZoneInfo(str(name))
    except Exception:
        return None


def cron_to_trigger(expr: str, timezone=None) -> CronTrigger:
    # Quartz 6 段：sec min hour dom mon dow
    sec, minute, hour, dom, mon, dow = expr.split()
    dom = "*" if dom == "?" else dom
    dow = "*" if dow == "?" else dow
    return CronTrigger(second=sec, minute=minute, hour=hour,
                       day=dom, month=mon, day_of_week=dow,
                       timezone=timezone)
