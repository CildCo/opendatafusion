from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from odf.models import (Alert, ContractCheck, Job, Notification,
                        NotificationRead, PipelineNodeRun, QueryRun,
                        WebhookDelivery)
from odf.settings import get_settings

POLICY_KEYS = ("query_run", "job", "notification", "alert",
               "webhook_delivery", "contract_check")
TERMINAL_JOBS = ("success", "failed", "skipped", "cancelled")
TERMINAL_DELIVERIES = ("delivered", "failed")
DEFAULT_DAYS = {"query_run": 30, "job": 90, "notification": 30,
                "alert": 180, "webhook_delivery": 30,
                "contract_check": 90}


def policies(overrides=None):
    settings = get_settings()
    out = {}
    for key in POLICY_KEYS:
        value = getattr(settings, "retention_%s_days" % key,
                        DEFAULT_DAYS[key])
        out[key] = max(0, int(value))
    for key, value in (overrides or {}).items():
        if key not in out:
            continue
        try:
            days = int(value)
        except (TypeError, ValueError):
            raise ValueError("retention days must be a number")
        if days < 0:
            raise ValueError("retention days cannot be negative")
        out[key] = days
    return out


def _cutoff(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _query_condition(days):
    return QueryRun.created_at < _cutoff(days)


def _job_condition(days):
    return (Job.status.in_(TERMINAL_JOBS)) & \
        (Job.created_at < _cutoff(days))


def _notification_condition(days):
    return Notification.created_at < _cutoff(days)


def _alert_condition(days):
    return (Alert.status == "closed") & \
        (Alert.created_at < _cutoff(days))


def _contract_condition(days):
    return ContractCheck.checked_at < _cutoff(days)


def _delivery_condition(days):
    return (WebhookDelivery.status.in_(TERMINAL_DELIVERIES)) & \
        (WebhookDelivery.created_at < _cutoff(days))


CONDITIONS = {
    "query_run": _query_condition,
    "job": _job_condition,
    "notification": _notification_condition,
    "alert": _alert_condition,
    "webhook_delivery": _delivery_condition,
    "contract_check": _contract_condition,
}


def _count(session, key, policy):
    if not policy:
        return 0
    model = {"query_run": QueryRun, "job": Job,
             "notification": Notification, "alert": Alert,
             "webhook_delivery": WebhookDelivery,
             "contract_check": ContractCheck}[key]
    return session.query(model).filter(CONDITIONS[key](policy)).count()


def counts(session, overrides=None):
    rules = policies(overrides)
    return {key: _count(session, key, rules[key]) for key in POLICY_KEYS}


def _delete(session, key, policy):
    condition = CONDITIONS[key](policy)
    if key == "job":
        job_ids = select(Job.id).where(condition)
        session.execute(delete(PipelineNodeRun).where(
            PipelineNodeRun.job_id.in_(job_ids)))
        return session.execute(delete(Job).where(condition)).rowcount
    if key == "notification":
        note_ids = select(Notification.id).where(condition)
        session.execute(delete(NotificationRead).where(
            NotificationRead.notification_id.in_(note_ids)))
        return session.execute(
            delete(Notification).where(condition)).rowcount
    model = {"query_run": QueryRun, "alert": Alert,
             "webhook_delivery": WebhookDelivery,
             "contract_check": ContractCheck}[key]
    return session.execute(delete(model).where(condition)).rowcount


def prune(session, overrides=None, apply=False):
    rules = policies(overrides)
    out = {}
    for key in POLICY_KEYS:
        policy = rules[key]
        matched = _count(session, key, policy)
        removed = 0
        if apply and matched:
            removed = int(_delete(session, key, policy) or 0)
        out[key] = {"days": policy, "matched": matched, "removed": removed}
    if apply:
        session.commit()
    return out


_last_run = None


def run_daily(session, now=None):
    global _last_run
    now = now or datetime.now(timezone.utc)
    day = now.date()
    if _last_run == day:
        return None
    _last_run = day
    result = prune(session, apply=True)
    removed = {key: value["removed"] for key, value in result.items()
               if value["removed"]}
    if removed:
        from odf.services.audit import write_audit
        write_audit(session, "scheduler", "retention_prune", "retention",
                    {"removed": removed})
    return result
