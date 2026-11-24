from apscheduler.triggers.cron import CronTrigger


def cron_to_trigger(expr: str) -> CronTrigger:
    # Quartz 6 段：sec min hour dom mon dow
    sec, minute, hour, dom, mon, dow = expr.split()
    dom = "*" if dom == "?" else dom
    dow = "*" if dow == "?" else dow
    return CronTrigger(second=sec, minute=minute, hour=hour,
                       day=dom, month=mon, day_of_week=dow)
