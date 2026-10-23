from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from odf.models import Flow, FlowRun

_LOCKS = set()
_LOCK_CONNS = {}
_sched = BackgroundScheduler()


def start_scheduler():
    if not _sched.running:
        _sched.start()


def stop_scheduler():
    if _sched.running:
        _sched.shutdown(wait=False)


def schedule(session, flow_id: int) -> None:
    flow = session.get(Flow, flow_id)
    if not flow or not flow.cron:
        return
    _sched.add_job(_run_job, cron_to_trigger(flow.cron), args=[flow_id],
                   id=str(flow_id), replace_existing=True)


def unschedule(flow_id: int) -> None:
    try:
        _sched.remove_job(str(flow_id))
    except Exception:
        pass


def _run_job(flow_id: int) -> None:
    from odf.db import SessionLocal
    with SessionLocal() as s:
        try:
            trigger(s, flow_id, "scheduler")
        except Exception:
            pass


def cron_to_trigger(expr: str) -> CronTrigger:
    # Quartz 6 段：sec min hour dom mon dow
    sec, minute, hour, dom, mon, dow = expr.split()
    dom = "*" if dom == "?" else dom
    dow = "*" if dow == "?" else dow
    return CronTrigger(second=sec, minute=minute, hour=hour,
                       day=dom, month=mon, day_of_week=dow)


def claim_run(session, flow_id: int) -> bool:
    if session.bind.dialect.name == "postgresql":
        conn = session.get_bind().connect()
        got = conn.execute(text("select pg_try_advisory_lock(:k)"),
                           {"k": 900000 + flow_id}).scalar()
        if got:
            _LOCK_CONNS[flow_id] = conn
        else:
            conn.close()
        return bool(got)
    if flow_id in _LOCKS:
        return False
    _LOCKS.add(flow_id)
    return True


def release_run(session, flow_id: int) -> None:
    if session.bind.dialect.name == "postgresql":
        conn = _LOCK_CONNS.pop(flow_id, None)
        if conn is not None:
            conn.execute(text("select pg_advisory_unlock(:k)"),
                         {"k": 900000 + flow_id})
            conn.close()
    else:
        _LOCKS.discard(flow_id)


def trigger(session, flow_id: int, actor: str) -> FlowRun:
    flow = session.get(Flow, flow_id)
    if not flow or flow.status != 1:
        raise RuntimeError("flow %s is disabled" % flow_id)
    if not claim_run(session, flow_id):
        raise RuntimeError("flow %s is already running" % flow_id)
    try:
        from odf.workers.etl import run_flow
        return run_flow(session, flow_id, actor)
    except Exception:
        release_run(session, flow_id)
        raise
