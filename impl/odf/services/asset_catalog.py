from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from odf.models import (ApiCallStat, Asset, ContractCheck, Domain, Job,
                        LineageEdge)
from odf.services.audit import write_audit

CERTIFICATIONS = {"none", "certified"}
LIFECYCLES = {"active", "deprecated", "archived"}


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso(value):
    value = _aware(value)
    return value.isoformat() if value else None


def _usage_maps(session, project_id):
    since = _now() - timedelta(days=30)
    runs = dict(session.query(Job.asset_id, func.count(Job.id))
                .filter(Job.project_id == project_id,
                        Job.asset_id.isnot(None))
                .group_by(Job.asset_id).all())
    calls = dict(session.query(ApiCallStat.api_id, func.sum(ApiCallStat.count))
                 .filter(ApiCallStat.day >= since.date())
                 .group_by(ApiCallStat.api_id).all())
    downstream = dict(session.query(LineageEdge.from_id,
                                    func.count(LineageEdge.id))
                      .filter(LineageEdge.project_id == project_id,
                              LineageEdge.from_type == "asset",
                              LineageEdge.from_column.is_(None))
                      .group_by(LineageEdge.from_id).all())
    checks = {}
    for row in (session.query(ContractCheck)
                .filter(ContractCheck.project_id == project_id)
                .order_by(ContractCheck.asset_id, ContractCheck.id.desc())
                .all()):
        checks.setdefault(row.asset_id, row)
    domains = {d.id: d.name for d in
               session.query(Domain).filter_by(project_id=project_id).all()}
    return {"runs": runs, "calls": calls, "downstream": downstream,
            "checks": checks, "domains": domains}


def _usage_for(asset, maps):
    runs = int(maps["runs"].get(asset.id) or 0)
    calls = int(maps["calls"].get(asset.id) or 0)
    downstream = int(maps["downstream"].get(str(asset.id)) or 0)
    return {"runs": runs, "api_calls_30d": calls,
            "downstream": downstream,
            "total": runs + calls + downstream}


def _factor(key, weight, ok, detail=""):
    return {"key": key, "weight": weight, "ok": bool(ok),
            "score": weight if ok else 0, "detail": detail}


def trust(session, asset, maps=None):
    maps = maps or _usage_maps(session, asset.project_id)
    usage = _usage_for(asset, maps)
    check = maps["checks"].get(asset.id)
    contract = asset.contract_json or {}
    usage_ok = usage["total"] >= 1
    factors = [
        _factor("certified", 30, asset.certification == "certified",
                asset.certified_by or ""),
        _factor("owner", 10, bool((asset.owner or "").strip()), asset.owner),
        _factor("domain", 10, bool(asset.domain_id),
                maps["domains"].get(asset.domain_id, "")),
        _factor("contract", 15, bool(contract),
                ", ".join(sorted(contract)[:4])),
        _factor("check", 15, bool(check and check.status == "ok"),
                check.status if check else "not checked"),
        _factor("usage", 20, usage_ok, str(usage["total"])),
    ]
    score = sum(item["score"] for item in factors)
    level = ("trusted" if score >= 80 else "good" if score >= 60
             else "fair" if score >= 40 else "low")
    return {"score": score, "level": level, "factors": factors,
            "usage": usage, "domain_name": maps["domains"].get(asset.domain_id),
            "last_checked_at": _iso(check.checked_at) if check else None,
            "checked_at": _iso(_now())}


def _serialize(session, asset, maps):
    return {"id": asset.id, "key": asset.key, "type": asset.type,
            "name": asset.name, "description": asset.description or "",
            "owner": asset.owner, "domain_id": asset.domain_id,
            "domain_name": maps["domains"].get(asset.domain_id),
            "published": bool(asset.published_version_id),
            "enabled": bool(asset.enabled), "cron": asset.cron,
            "certification": asset.certification or "none",
            "certified_by": asset.certified_by,
            "certified_at": _iso(asset.certified_at),
            "lifecycle": asset.lifecycle or "active",
            "lifecycle_note": asset.lifecycle_note or "",
            "updated_at": _iso(asset.updated_at),
            "created_at": _iso(asset.created_at),
            "trust": trust(session, asset, maps)}


def _query(session, project_id, q=None, type=None, certification=None,
           lifecycle=None):
    query = session.query(Asset).filter(Asset.project_id == project_id)
    if type:
        query = query.filter(Asset.type == type)
    if certification:
        query = query.filter(Asset.certification == certification)
    if lifecycle:
        query = query.filter(Asset.lifecycle == lifecycle)
    else:
        query = query.filter(Asset.lifecycle != "archived")
    text = (q or "").strip()
    if text:
        like = "%%%s%%" % text
        query = query.filter(
            (Asset.name.ilike(like)) | (Asset.key.ilike(like))
            | (Asset.description.ilike(like)) | (Asset.owner.ilike(like)))
    return query


def _relevance(item, text):
    if not text:
        return 0
    name = item["name"].casefold()
    key = item["key"].casefold()
    needle = text.casefold()
    score = 0
    if name == needle:
        score += 100
    elif name.startswith(needle):
        score += 60
    elif needle in name:
        score += 30
    if key == needle:
        score += 40
    elif needle in key:
        score += 15
    if item["certification"] == "certified":
        score += 20
    if item["lifecycle"] == "active":
        score += 5
    return score + item["trust"]["score"] * 0.3 + min(
        item["trust"]["usage"]["total"], 50) * 0.2


def list_assets(session, project_id, q=None, type=None, certification=None,
                lifecycle=None, sort="relevance", limit=100, offset=0):
    if certification and certification not in CERTIFICATIONS:
        raise ValueError("invalid certification")
    if lifecycle and lifecycle not in LIFECYCLES:
        raise ValueError("invalid lifecycle")
    sort = sort if sort in ("relevance", "trust", "recent", "usage") \
        else "relevance"
    limit = max(1, min(int(limit or 100), 200))
    offset = max(0, int(offset or 0))
    maps = _usage_maps(session, project_id)
    rows = _query(session, project_id, q, type, certification,
                  lifecycle).all()
    items = [_serialize(session, asset, maps) for asset in rows]
    text = (q or "").strip()
    if sort == "trust":
        items.sort(key=lambda item: (-item["trust"]["score"],
                                     -item["trust"]["usage"]["total"],
                                     item["name"].casefold()))
    elif sort == "recent":
        items.sort(key=lambda item: (item["updated_at"] or "",
                                     item["id"]), reverse=True)
    elif sort == "usage":
        items.sort(key=lambda item: (-item["trust"]["usage"]["total"],
                                     -item["trust"]["score"],
                                     item["name"].casefold()))
    else:
        items.sort(key=lambda item: (-_relevance(item, text),
                                     item["name"].casefold()))
    return {"items": items[offset:offset + limit], "total": len(items),
            "recommended": _recommended(items, limit=5)}


def _recommended(items, limit=5):
    active = [item for item in items
              if item["lifecycle"] == "active" and item["published"]]
    active.sort(key=lambda item: (-item["trust"]["score"],
                                  -item["trust"]["usage"]["total"],
                                  item["name"].casefold()))
    return active[:limit]


def recommended(session, project_id, limit=6):
    limit = max(1, min(int(limit or 6), 20))
    maps = _usage_maps(session, project_id)
    rows = (_query(session, project_id).filter(Asset.lifecycle == "active")
            .all())
    items = [_serialize(session, asset, maps) for asset in rows
             if asset.published_version_id]
    return _recommended(items, limit)


def similar(session, project_id, asset_id, limit=6):
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    maps = _usage_maps(session, project_id)
    neighbors = set()
    for edge in (session.query(LineageEdge)
                 .filter(LineageEdge.project_id == project_id,
                         LineageEdge.from_id == str(asset.id)).all()):
        try:
            neighbors.add(int(edge.to_id))
        except (TypeError, ValueError):
            pass
    for edge in (session.query(LineageEdge)
                 .filter(LineageEdge.project_id == project_id,
                         LineageEdge.to_id == str(asset.id)).all()):
        try:
            neighbors.add(int(edge.from_id))
        except (TypeError, ValueError):
            pass
    words = {word for word in asset.name.casefold().replace("_", " ").split()
             if len(word) > 2}
    scored = []
    for row in (_query(session, project_id).filter(Asset.id != asset.id)
                .all()):
        score = 0
        if row.id in neighbors:
            score += 60
        if row.domain_id and row.domain_id == asset.domain_id:
            score += 35
        if row.type == asset.type:
            score += 10
        if row.owner == asset.owner:
            score += 10
        if row.certification == "certified":
            score += 5
        other = {word for word in row.name.casefold().replace("_", " ").split()
                 if len(word) > 2}
        score += min(len(words & other), 3) * 8
        if score <= 0:
            continue
        item = _serialize(session, row, maps)
        scored.append((score + item["trust"]["score"] * 0.1, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["name"].casefold()))
    return [item for _, item in scored[:max(1, min(int(limit), 20))]]


def certify(session, project_id, asset_id, certified, actor, note=""):
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    if not (asset.lifecycle or "active") == "active" and certified:
        raise ValueError("restore the asset before certifying it")
    if certified:
        asset.certification = "certified"
        asset.certified_by = actor[:64]
        asset.certified_at = _now()
    else:
        asset.certification = "none"
        asset.certified_by = None
        asset.certified_at = None
    session.commit()
    write_audit(session, actor,
                "certify_asset" if certified else "revoke_certification",
                str(asset.id), {"note": (note or "")[:500]})
    session.refresh(asset)
    return _serialize(session, asset, _usage_maps(session, project_id))


def set_lifecycle(session, project_id, asset_id, lifecycle, note, actor):
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    if lifecycle not in LIFECYCLES:
        raise ValueError("invalid lifecycle")
    if lifecycle != "active" and not (note or "").strip():
        raise ValueError("a lifecycle note is required")
    asset.lifecycle = lifecycle
    asset.lifecycle_note = (note or "")[:500]
    asset.lifecycle_changed_at = _now()
    if lifecycle != "active" and asset.certification == "certified":
        asset.certification = "none"
        asset.certified_by = None
        asset.certified_at = None
    session.commit()
    write_audit(session, actor, "set_asset_lifecycle", str(asset.id),
                {"lifecycle": lifecycle, "note": asset.lifecycle_note})
    session.refresh(asset)
    return _serialize(session, asset, _usage_maps(session, project_id))
