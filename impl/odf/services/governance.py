import re
from datetime import datetime, timedelta, timezone

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _domain(session, project_id, domain_id):
    from odf.models import Domain
    row = session.get(Domain, domain_id) if domain_id else None
    if row and row.project_id != project_id:
        row = None
    return row


def list_domains(session, project_id):
    from odf.models import Domain
    return (session.query(Domain).filter_by(project_id=project_id)
            .order_by(Domain.name).all())


def create_domain(session, project_id, name, description="", owner=""):
    from odf.models import Domain
    name = (name or "").strip()
    if not name:
        raise ValueError("domain name is required")
    if (session.query(Domain).filter_by(project_id=project_id,
                                        name=name).first()):
        raise ValueError("domain already exists")
    row = Domain(project_id=project_id, name=name[:128],
                 description=(description or "")[:2000],
                 owner=(owner or "")[:64])
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_domain(session, project_id, domain_id, name=None,
                  description=None, owner=None):
    row = _domain(session, project_id, domain_id)
    if not row:
        raise ValueError("domain not found")
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("domain name is required")
        clash = (session.query(type(row)).filter(
            type(row).project_id == project_id, type(row).name == name,
            type(row).id != row.id).first())
        if clash:
            raise ValueError("domain already exists")
        row.name = name[:128]
    if description is not None:
        row.description = description[:2000]
    if owner is not None:
        row.owner = owner[:64]
    session.commit()
    session.refresh(row)
    return row


def delete_domain(session, project_id, domain_id):
    from odf.models import Asset, Dataset, GlossaryTerm
    row = _domain(session, project_id, domain_id)
    if not row:
        raise ValueError("domain not found")
    session.query(Asset).filter(Asset.project_id == project_id,
                                Asset.domain_id == domain_id).update(
        {Asset.domain_id: None}, synchronize_session=False)
    session.query(Dataset).filter(Dataset.domain_id == domain_id).update(
        {Dataset.domain_id: None}, synchronize_session=False)
    session.query(GlossaryTerm).filter(
        GlossaryTerm.project_id == project_id,
        GlossaryTerm.domain_id == domain_id).update(
        {GlossaryTerm.domain_id: None}, synchronize_session=False)
    session.delete(row)
    session.commit()


def list_terms(session, project_id, domain_id=None):
    from odf.models import GlossaryTerm
    q = session.query(GlossaryTerm).filter_by(project_id=project_id)
    if domain_id is not None:
        q = q.filter_by(domain_id=domain_id)
    return q.order_by(GlossaryTerm.term).all()


def create_term(session, project_id, term, definition="", domain_id=None,
                owner=""):
    from odf.models import GlossaryTerm
    term = (term or "").strip()
    if not term:
        raise ValueError("term is required")
    if domain_id is not None and not _domain(session, project_id, domain_id):
        raise ValueError("domain not found")
    if (session.query(GlossaryTerm)
            .filter_by(project_id=project_id, term=term).first()):
        raise ValueError("term already exists")
    row = GlossaryTerm(project_id=project_id, term=term[:128],
                       definition=(definition or "")[:4000],
                       domain_id=domain_id, owner=(owner or "")[:64])
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_term(session, project_id, term_id, term=None, definition=None,
                domain_id=None, owner=None):
    from odf.models import GlossaryTerm
    row = session.get(GlossaryTerm, term_id)
    if not row or row.project_id != project_id:
        raise ValueError("term not found")
    if term is not None:
        term = term.strip()
        if not term:
            raise ValueError("term is required")
        clash = (session.query(GlossaryTerm).filter(
            GlossaryTerm.project_id == project_id,
            GlossaryTerm.term == term,
            GlossaryTerm.id != row.id).first())
        if clash:
            raise ValueError("term already exists")
        row.term = term[:128]
    if definition is not None:
        row.definition = definition[:4000]
    if domain_id is not None:
        if domain_id and not _domain(session, project_id, domain_id):
            raise ValueError("domain not found")
        row.domain_id = domain_id or None
    if owner is not None:
        row.owner = owner[:64]
    session.commit()
    session.refresh(row)
    return row


def delete_term(session, project_id, term_id):
    from odf.models import GlossaryTerm
    row = session.get(GlossaryTerm, term_id)
    if not row or row.project_id != project_id:
        raise ValueError("term not found")
    session.delete(row)
    session.commit()


def _clean_contract(raw):
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("contract must be an object")
    out = {}
    for key in ("owner", "sla", "notes"):
        value = raw.get(key)
        if value is not None:
            out[key] = str(value)[:4000]
    for key in ("enforce", "allow_extra"):
        if key in raw:
            out[key] = bool(raw[key])
    if "freshness" in raw and raw["freshness"] is not None:
        value = raw["freshness"]
        if not isinstance(value, dict):
            raise ValueError("freshness must be an object")
        column = value.get("column")
        if not isinstance(column, str) or not _IDENT.match(column):
            raise ValueError("freshness column must be an identifier")
        try:
            hours = int(value.get("max_hours"))
        except (TypeError, ValueError):
            raise ValueError("freshness max_hours must be a number")
        if not 1 <= hours <= 8760:
            raise ValueError("freshness max_hours must be 1..8760")
        out["freshness"] = {"column": column, "max_hours": hours}
    for key in ("schema", "quality"):
        value = raw.get(key)
        if value is None:
            continue
        if not isinstance(value, list):
            raise ValueError("%s must be an array" % key)
        cleaned = []
        for item in value[:200]:
            if key == "schema":
                if isinstance(item, str):
                    cleaned.append({"name": item[:128]})
                elif isinstance(item, dict) and \
                        isinstance(item.get("name"), str):
                    cleaned.append({
                        "name": item["name"][:128],
                        "type": str(item.get("type") or "")[:64],
                        "required": bool(item.get("required"))})
                else:
                    raise ValueError("schema columns need a name")
            else:
                cleaned.append(item)
        out[key] = cleaned
    import json
    if len(json.dumps(out, default=str)) > 50000:
        raise ValueError("contract is too large")
    return out


def asset_governance(session, project_id, asset_id):
    from odf.models import Asset, Domain
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    domain = session.get(Domain, asset.domain_id) \
        if asset.domain_id else None
    return {"asset_id": asset.id, "type": asset.type, "owner": asset.owner,
            "domain_id": asset.domain_id,
            "domain_name": domain.name if domain else None,
            "contract": asset.contract_json or {}}


def update_asset_governance(session, project_id, asset_id, domain_id=None,
                            contract=None):
    from odf.models import Asset
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    if domain_id is not None:
        if domain_id and not _domain(session, project_id, domain_id):
            raise ValueError("domain not found")
        asset.domain_id = domain_id or None
    if contract is not None:
        asset.contract_json = _clean_contract(contract)
    session.commit()
    session.refresh(asset)
    return asset_governance(session, project_id, asset_id)


def table_governance(session, project_id, dataset_id):
    from odf.models import Dataset, Domain
    row = session.get(Dataset, dataset_id)
    if not row:
        raise ValueError("dataset not found")
    from odf.models import Datasource
    ds = session.get(Datasource, row.datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("dataset not found")
    domain = session.get(Domain, row.domain_id) if row.domain_id else None
    return {"dataset_id": row.id,
            "schema": row.schema_name, "table": row.table_name,
            "domain_id": row.domain_id,
            "domain_name": domain.name if domain else None}


def update_table_governance(session, project_id, dataset_id, domain_id=None):
    from odf.models import Dataset
    row = session.get(Dataset, dataset_id)
    if not row:
        raise ValueError("dataset not found")
    from odf.models import Datasource
    ds = session.get(Datasource, row.datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("dataset not found")
    if domain_id is not None:
        if domain_id and not _domain(session, project_id, domain_id):
            raise ValueError("domain not found")
        row.domain_id = domain_id or None
    session.commit()
    return table_governance(session, project_id, dataset_id)


def _mentions(node, target_id):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("dataset_id", "metric_id", "api_id", "dashboard_id",
                       "app_id", "pipeline_id") and value == target_id:
                return True
            if _mentions(value, target_id):
                return True
    elif isinstance(node, list):
        return any(_mentions(item, target_id) for item in node)
    return False


def asset_usage(session, project_id, asset_id):
    from odf.models import (ApiCallStat, Asset, AssetVersion, Job,
                            LineageEdge)
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    versions = (session.query(AssetVersion)
                .filter(AssetVersion.asset_id != asset_id).all())
    versions = [v for v in versions
                if session.get(Asset, v.asset_id)
                and session.get(Asset, v.asset_id).project_id == project_id]
    refs = []
    for version in versions:
        if _mentions(version.content_json or {}, asset_id):
            row = session.get(Asset, version.asset_id)
            refs.append({"id": row.id, "asset_id": row.id, "type": row.type,
                         "name": row.name})
    runs = session.query(Job).filter_by(asset_id=asset_id).count()
    downstream = (session.query(LineageEdge)
                  .filter(LineageEdge.project_id == project_id,
                          LineageEdge.from_type == "asset",
                          LineageEdge.from_id == str(asset_id),
                          LineageEdge.from_column.is_(None)).count())
    calls = 0
    errors = 0
    if asset.type == "api":
        since = datetime.now(timezone.utc) - timedelta(days=30)
        rows = (session.query(ApiCallStat)
                .filter(ApiCallStat.api_id == asset_id,
                        ApiCallStat.day >= since.date()).all())
        calls = sum(row.count for row in rows)
        errors = sum(row.errors for row in rows)
    return {"asset_id": asset.id, "references": refs,
            "reference_count": len(refs), "runs": runs,
            "downstream": downstream, "api_calls_30d": calls,
            "api_errors_30d": errors}
