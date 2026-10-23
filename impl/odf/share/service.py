import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from odf.appstudio.service import app_data
from odf.assets.service import get_asset
from odf.dashboards.service import dashboard_data
from odf.models import AssetVersion, ShareLink
from odf.services.audit import write_audit

ASSET_TYPES = {"app", "dashboard"}


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt and dt.tzinfo else (
        dt.replace(tzinfo=timezone.utc) if dt else None)


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _asset(session, project_id, asset_id, asset_type):
    if asset_type not in ASSET_TYPES:
        raise ValueError("unsupported asset type")
    a = get_asset(session, asset_id)
    if not a or a.type != asset_type or a.project_id != project_id:
        raise ValueError("asset not found")
    return a


def create_share(session, project_id, asset_id, asset_type, days, actor):
    a = _asset(session, project_id, asset_id, asset_type)
    if not a.published_version_id:
        raise ValueError("asset is not published")
    if not isinstance(days, int) or isinstance(days, bool) or \
            not 1 <= days <= 30:
        raise ValueError("expires_days must be 1..30")
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(days=days)
    sh = ShareLink(project_id=project_id, asset_id=a.id,
                   asset_type=asset_type, token_hash=_hash(token),
                   created_by=actor, expires_at=expires)
    session.add(sh)
    session.commit()
    session.refresh(sh)
    write_audit(session, actor, "create_share", str(a.id),
                {"share_id": sh.id, "asset_type": asset_type,
                 "expires_at": expires.isoformat()})
    return {"id": sh.id, "token": token, "expires_at": expires}


def list_shares(session, project_id, asset_id, asset_type):
    _asset(session, project_id, asset_id, asset_type)
    rows = (session.query(ShareLink)
            .filter_by(project_id=project_id, asset_id=asset_id,
                       asset_type=asset_type)
            .order_by(ShareLink.id.desc()).all())
    now = _now()
    return [{"id": s.id, "created_by": s.created_by,
             "created_at": _aware(s.created_at),
             "expires_at": _aware(s.expires_at),
             "revoked_at": _aware(s.revoked_at),
             "active": s.revoked_at is None and
                       _aware(s.expires_at) > now} for s in rows]


def revoke_share(session, project_id, asset_id, asset_type, share_id, actor):
    _asset(session, project_id, asset_id, asset_type)
    sh = session.get(ShareLink, share_id)
    if not sh or sh.project_id != project_id or sh.asset_id != asset_id \
            or sh.asset_type != asset_type:
        raise ValueError("share not found")
    if sh.revoked_at is None:
        sh.revoked_at = _now()
        session.commit()
    write_audit(session, actor, "revoke_share", str(asset_id),
                {"share_id": sh.id, "asset_type": asset_type,
                 "expires_at": _aware(sh.expires_at).isoformat()})
    return {"id": sh.id, "revoked": True}


def resolve(session, token):
    if not isinstance(token, str) or not token:
        raise ValueError("share not found")
    sh = (session.query(ShareLink)
          .filter_by(token_hash=_hash(token)).first())
    if not sh or sh.revoked_at is not None or \
            _aware(sh.expires_at) <= _now():
        raise ValueError("share not found")
    a = get_asset(session, sh.asset_id)
    if not a or a.type != sh.asset_type or a.project_id != sh.project_id:
        raise ValueError("share not found")
    if not a.published_version_id:
        raise ValueError("share not found")
    v = session.get(AssetVersion, a.published_version_id)
    if not v:
        raise ValueError("share not found")
    return a, v.content_json


def _public_content(kind, content):
    if kind != "app":
        return content
    return {**content,
            "pages": [{**p,
                       "components": [c for c in p.get("components") or []
                                      if c.get("type") != "form"]}
                      for p in content.get("pages") or []]}


def _public_item(item):
    if not isinstance(item, dict):
        return item
    out = {k: v for k, v in item.items() if k != "sql"}
    if out.get("error"):
        out["error"] = "数据加载失败"
    return out


def _public_result(result, list_key):
    return {**result,
            list_key: {k: _public_item(v)
                       for k, v in (result.get(list_key) or {}).items()}}


def public_view(session, token):
    a, content = resolve(session, token)
    return {"kind": a.type, "name": a.name,
            "content": _public_content(a.type, content)}


def public_data(session, token, page_id=None, params=None, limit=100):
    a, content = resolve(session, token)
    if a.type == "app":
        result = app_data(session, a.id, page_id=page_id, params=params,
                          content=_public_content("app", content),
                          limit=limit, published_only=True,
                          role="viewer")
        return _public_result(result, "components")
    result = dashboard_data(session, a.id, params=params, limit=limit,
                            published_only=True, role="viewer")
    return _public_result(result, "widgets")
