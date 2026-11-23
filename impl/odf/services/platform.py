"""Platform-wide administration settings and derived runtime overrides."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from odf.models import (Alert, Asset, Job, PlatformSetting, Project, User)
from odf.services.audit import write_audit
from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.settings import replace_overrides

MASK = "********"

DEFAULTS = {
    "brand": {
        "name": "OpenDataFusion",
        "color": "#1d4ed8",
        "welcome_title": "",
        "welcome_text": "",
        "default_locale": "zh",
        "announcement": "",
    },
    "login": {
        "session_hours": 0,
        "mfa_required_roles": [],
    },
    "identity": {
        "oidc": {
            "enabled": False, "issuer": "", "client_id": "",
            "client_secret": "", "redirect_uri": "",
            "scopes": "openid profile email", "auto_provision": True,
        },
        "ldap": {
            "enabled": False, "url": "", "user_dn_template": "",
            "bind_dn": "", "bind_password": "", "auto_provision": True,
        },
    },
    "engines": {
        "spark_image": "",
        "flink_sql_gateway_url": "",
        "sql_write_enabled": None,
    },
    "cdc": {
        "topic_prefix": "",
        "kafka_bootstrap": "",
    },
    "features": {
        "workbench": True, "cdc": True, "tools": True,
        "apps": True, "dashboards": True,
    },
    "audit": {
        "retention_days": 0,
        "siem_url": "",
        "siem_token": "",
        "siem_cursor": 0,
    },
    "alerts": {
        "webhook_url": "",
    },
}

SECRET_PATHS = (("identity", "oidc", "client_secret"),
                ("identity", "ldap", "bind_password"),
                ("audit", "siem_token"))


def _merge(base, patch):
    out = deepcopy(base)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _row(session):
    row = session.get(PlatformSetting, 1)
    if not row:
        row = PlatformSetting(id=1, settings_json={})
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def get_doc(session, mask=True):
    row = _row(session)
    doc = _merge(DEFAULTS, row.settings_json or {})
    if mask:
        for path in SECRET_PATHS:
            node = doc
            for key in path[:-1]:
                node = node.get(key, {})
            value = node.get(path[-1]) or ""
            node[path[-1]] = MASK if value else ""
    else:
        for path in SECRET_PATHS:
            node = doc
            for key in path[:-1]:
                node = node.get(key, {})
            value = node.get(path[-1]) or ""
            if value and value != MASK:
                try:
                    node[path[-1]] = decrypt_secret(value)
                except Exception:
                    node[path[-1]] = ""
    return doc


def update_doc(session, patch, actor=""):
    row = _row(session)
    current = deepcopy(row.settings_json or {})
    clean = deepcopy(patch or {})
    for path in SECRET_PATHS:
        node = clean
        for key in path[:-1]:
            node = node.get(key)
            if not isinstance(node, dict):
                node = None
                break
        if not isinstance(node, dict):
            continue
        value = node.get(path[-1])
        if value in (None, "", MASK):
            node.pop(path[-1], None)
        else:
            node[path[-1]] = encrypt_secret(str(value))
    merged = _merge(current, clean)
    row.settings_json = merged
    session.commit()
    apply_runtime(session)
    write_audit(session, actor, "update_platform_settings", "platform",
                {"sections": sorted(clean.keys())})
    return get_doc(session)


def public_doc(session):
    doc = get_doc(session, mask=True)
    return {
        "brand": doc["brand"],
        "features": doc["features"],
        "announcement": doc["brand"].get("announcement", ""),
        "default_locale": doc["brand"].get("default_locale", "zh"),
    }


def identity_doc(session):
    return get_doc(session, mask=False)["identity"]


def session_hours(session):
    hours = get_doc(session, mask=True)["login"].get("session_hours") or 0
    return int(hours) if hours and int(hours) > 0 else None


def mfa_roles(session):
    return set(get_doc(session, mask=True)["login"].get(
        "mfa_required_roles") or [])


def apply_runtime(session):
    doc = get_doc(session, mask=False)
    overrides = {}
    oidc = doc["identity"]["oidc"]
    if oidc.get("enabled") and oidc.get("issuer") \
            and oidc.get("client_id") and oidc.get("redirect_uri"):
        overrides.update({
            "oidc_issuer": oidc["issuer"],
            "oidc_client_id": oidc["client_id"],
            "oidc_client_secret": oidc.get("client_secret", ""),
            "oidc_redirect_uri": oidc["redirect_uri"],
            "oidc_scopes": oidc.get("scopes") or "openid profile email",
            "oidc_auto_provision": bool(oidc.get("auto_provision", True)),
        })
    else:
        overrides.update({"oidc_issuer": "", "oidc_client_id": "",
                          "oidc_client_secret": "",
                          "oidc_redirect_uri": ""})
    ldap = doc["identity"]["ldap"]
    if ldap.get("enabled") and ldap.get("url") \
            and ldap.get("user_dn_template"):
        overrides.update({
            "ldap_url": ldap["url"],
            "ldap_user_dn_template": ldap["user_dn_template"],
            "ldap_bind_dn": ldap.get("bind_dn", ""),
            "ldap_bind_password": ldap.get("bind_password", ""),
            "ldap_auto_provision": bool(ldap.get("auto_provision", True)),
        })
    else:
        overrides.update({"ldap_url": "", "ldap_user_dn_template": "",
                          "ldap_bind_dn": "", "ldap_bind_password": ""})
    engines = doc["engines"]
    if engines.get("spark_image"):
        overrides["spark_image"] = engines["spark_image"]
    if engines.get("flink_sql_gateway_url"):
        overrides["flink_sql_gateway_url"] = engines["flink_sql_gateway_url"]
    if engines.get("sql_write_enabled") is not None:
        overrides["engine_sql_write_enabled"] = bool(
            engines["sql_write_enabled"])
    hours = doc["login"].get("session_hours") or 0
    if hours and int(hours) > 0:
        overrides["token_ttl_hours"] = int(hours)
    replace_overrides(overrides)
    return overrides


def is_platform_admin(user) -> bool:
    return bool(user and (getattr(user, "platform_admin", False)
                          or user.role == "admin"))


def overview(session):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    jobs = session.query(Job)
    assets = session.query(Asset)
    from odf.models import AuditLog
    mcp_rows = (session.query(AuditLog)
                .filter(AuditLog.actor == "mcp",
                        AuditLog.at >= since)
                .order_by(AuditLog.id.desc()).limit(6).all())
    return {
        "users": {
            "total": session.query(User).count(),
            "active": session.query(User).filter(
                User.active.is_(True)).count(),
            "platform_admins": session.query(User).filter(
                User.platform_admin.is_(True)).count(),
        },
        "projects": {
            "total": session.query(Project).count(),
            "active": session.query(Project).filter(
                Project.status == 1).count(),
        },
        "assets": {
            "total": assets.count(),
            "datasets": assets.filter(Asset.type == "dataset").count(),
            "metrics": assets.filter(Asset.type == "metric").count(),
            "dashboards": assets.filter(Asset.type == "dashboard").count(),
            "apps": assets.filter(Asset.type == "app").count(),
            "apis": assets.filter(Asset.type == "api").count(),
            "interfaces": assets.filter(Asset.type == "interface").count(),
        },
        "jobs": {
            "queued": jobs.filter(Job.status == "queued").count(),
            "running": jobs.filter(Job.status == "running").count(),
            "failed_24h": jobs.filter(Job.status == "failed",
                                      Job.run_at >= since).count(),
        },
        "alerts": {
            "open": session.query(Alert).filter(
                Alert.status == "open").count(),
        },
        "mcp": {
            "calls_24h": (session.query(AuditLog).filter(
                AuditLog.actor == "mcp", AuditLog.at >= since).count()),
            "recent": [{"action": row.action, "target": row.target,
                        "at": row.at.isoformat() if row.at else None}
                       for row in mcp_rows],
        },
    }
