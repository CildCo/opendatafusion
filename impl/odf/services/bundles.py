from datetime import datetime, timezone

BUNDLE_FORMAT = "odf-bundle"
BUNDLE_VERSION = 1
ASSET_TYPES = {"pipeline", "dataset", "metric", "api", "dashboard", "app",
               "model", "data_product"}


def _iso(value):
    return value.isoformat() if value else None


def export_bundle(session, project_id, asset_ids=None):
    from odf.models import (Asset, AssetVersion, Datasource, Domain,
                            GlossaryTerm, Project)
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("project not found")
    q = (session.query(Asset).filter(Asset.project_id == project_id,
                                     Asset.type.in_(ASSET_TYPES)))
    if asset_ids:
        q = q.filter(Asset.id.in_(asset_ids))
    assets = []
    for asset in q.order_by(Asset.id).all():
        version = (session.get(AssetVersion, asset.published_version_id)
                   if asset.published_version_id else None)
        if not version:
            continue
        domain = session.get(Domain, asset.domain_id) \
            if asset.domain_id else None
        assets.append({
            "id": asset.id,
            "type": asset.type, "key": asset.key, "name": asset.name,
            "description": asset.description, "owner": asset.owner,
            "enabled": asset.enabled, "cron": asset.cron,
            "domain": domain.name if domain else "",
            "contract": asset.contract_json or {},
            "content": version.content_json,
            "published_version": version.version,
        })
    datasources = [{"id": ds.id, "name": ds.name, "kind": ds.kind}
                   for ds in (session.query(Datasource)
                              .filter_by(project_id=project_id)
                              .order_by(Datasource.id).all())]
    domains = [{"name": row.name, "description": row.description,
                "owner": row.owner}
               for row in (session.query(Domain)
                            .filter_by(project_id=project_id)
                            .order_by(Domain.name).all())]
    domain_names = {row.id: row.name for row in
                    session.query(Domain)
                    .filter_by(project_id=project_id).all()}
    terms = [{"term": row.term, "definition": row.definition,
              "domain": domain_names.get(row.domain_id, ""),
              "owner": row.owner}
             for row in (session.query(GlossaryTerm)
                         .filter_by(project_id=project_id)
                         .order_by(GlossaryTerm.term).all())]
    return {
        "format": BUNDLE_FORMAT, "version": BUNDLE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project": {"code": project.code, "name": project.name,
                    "environment": project.environment},
        "datasources": datasources, "domains": domains,
        "terms": terms, "assets": assets,
    }


def _check_bundle(bundle):
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be an object")
    if bundle.get("format") != BUNDLE_FORMAT or \
            int(bundle.get("version") or 0) != BUNDLE_VERSION:
        raise ValueError("unsupported bundle format")
    assets = bundle.get("assets")
    if not isinstance(assets, list) or len(assets) > 5000:
        raise ValueError("bundle assets must be an array (max 5000)")
    for row in assets:
        if not isinstance(row, dict) or row.get("type") not in ASSET_TYPES:
            raise ValueError("unsupported asset type in bundle")
        if not isinstance(row.get("key"), str) or not row["key"].strip():
            raise ValueError("asset key is required")
        if not isinstance(row.get("content"), dict):
            raise ValueError("asset content must be an object")
    return assets


def validate_bundle(session, project_id, bundle):
    from odf.models import Asset, Datasource
    assets = _check_bundle(bundle)
    existing = {row.key: row.type for row in
                session.query(Asset).filter_by(project_id=project_id).all()}
    target = {(row.name, row.kind): row.id
              for row in session.query(Datasource)
              .filter_by(project_id=project_id).all()}
    unresolved = []
    for ds in bundle.get("datasources") or []:
        if (ds.get("name"), ds.get("kind")) not in target:
            unresolved.append("%s (%s)" % (ds.get("name"), ds.get("kind")))
    conflicts = []
    creates = updates = 0
    for row in assets:
        if row["key"] in existing:
            if existing[row["key"]] != row["type"]:
                conflicts.append("%s: type %s -> %s" % (
                    row["key"], existing[row["key"]], row["type"]))
            else:
                updates += 1
        else:
            creates += 1
    return {"assets": len(assets), "create": creates, "update": updates,
            "conflicts": conflicts, "unresolved_datasources": unresolved}


ASSET_REF_KEYS = ("dataset_id", "metric_id", "api_id", "dashboard_id",
                  "app_id", "pipeline_id")


def _remap(value, mapping, missing, asset_mapping=None):
    asset_mapping = asset_mapping or {}
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in ("datasource_id", "source_ds_id", "sink_ds_id") and \
                    isinstance(item, int):
                if item in mapping:
                    out[key] = mapping[item]
                else:
                    out[key] = None
                    missing.append(str(item))
            elif key == "asset_ids" and isinstance(item, list):
                out[key] = [asset_mapping.get(value, value)
                            if isinstance(value, int) else value
                            for value in item]
            elif key in ASSET_REF_KEYS and isinstance(item, int):
                if item in asset_mapping:
                    out[key] = asset_mapping[item]
                else:
                    out[key] = item
            else:
                out[key] = _remap(item, mapping, missing, asset_mapping)
        return out
    if isinstance(value, list):
        return [_remap(item, mapping, missing, asset_mapping)
                for item in value]
    return value


def import_bundle(session, project_id, bundle, actor):
    from odf.assets.service import create_asset, update_draft
    from odf.models import Asset, Datasource, Domain, GlossaryTerm, Project
    assets = _check_bundle(bundle)
    target_ds = {(row.name, row.kind): row.id
                 for row in session.query(Datasource)
                 .filter_by(project_id=project_id).all()}
    mapping = {}
    unresolved = []
    for ds in bundle.get("datasources") or []:
        key = (ds.get("name"), ds.get("kind"))
        if key in target_ds and isinstance(ds.get("id"), int):
            mapping[ds["id"]] = target_ds[key]
        else:
            unresolved.append("%s (%s)" % (ds.get("name"), ds.get("kind")))

    domains = {}
    for row in bundle.get("domains") or []:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        existing = (session.query(Domain)
                    .filter_by(project_id=project_id, name=name).first())
        if not existing:
            existing = Domain(project_id=project_id, name=name[:128],
                              description=(row.get("description") or "")[:2000],
                              owner=(row.get("owner") or "")[:64])
            session.add(existing)
            session.flush()
        domains[name] = existing.id

    for row in bundle.get("terms") or []:
        term = (row.get("term") or "").strip()
        if not term:
            continue
        existing = (session.query(GlossaryTerm)
                    .filter_by(project_id=project_id, term=term).first())
        if not existing:
            existing = GlossaryTerm(
                project_id=project_id, term=term[:128],
                definition=(row.get("definition") or "")[:4000],
                domain_id=domains.get(row.get("domain") or ""),
                owner=(row.get("owner") or "")[:64])
            session.add(existing)
        elif row.get("definition"):
            existing.definition = row["definition"][:4000]
    session.commit()

    created = updated = skipped = 0
    missing_refs = []
    asset_mapping = {}
    targets = []
    key_mapping = {}
    project = session.get(Project, project_id)

    def unique_key(source_key):
        key = source_key[:64]
        own = (session.query(Asset).filter_by(project_id=project_id,
                                              key=key).first())
        if own:
            return key
        other = session.query(Asset).filter_by(key=key).first()
        if not other:
            return key
        base = ("%s_%s" % (source_key, project.code))[:56]
        own = (session.query(Asset).filter_by(project_id=project_id,
                                              key=base).first())
        if own:
            return base
        other = session.query(Asset).filter_by(key=base).first()
        if not other:
            return base
        base = ("%s_%d" % (base, project_id))[:64]
        return base

    for row in assets:
        target_key = unique_key(row["key"])
        existing = (session.query(Asset)
                    .filter_by(project_id=project_id,
                               key=target_key).first())
        if existing and existing.type != row["type"]:
            skipped += 1
            continue
        if existing:
            target = existing
            updated += 1
        else:
            target = create_asset(
                session, project_id, row["type"],
                row.get("name") or row["key"], {}, actor,
                key=target_key, enabled=bool(row.get("enabled")))
            created += 1
        if isinstance(row.get("id"), int):
            asset_mapping[row["id"]] = target.id
        key_mapping[row["key"]] = target_key
        targets.append((row, target))

    import re
    from odf.transform.content import REF
    for row, target in targets:
        content = _remap(row["content"], mapping, missing_refs, asset_mapping)
        if row["type"] == "model":
            def repl(match):
                name = match.group(1).strip()
                return "{{ ref('%s') }}" % key_mapping.get(name, name)
            content["sql"] = REF.sub(repl, content.get("sql") or "")
        update_draft(session, target.id, content, actor,
                     note="bundle import")
        target.description = (row.get("description") or "")[:4000]
        target.owner = (row.get("owner") or actor)[:64]
        target.cron = row.get("cron") or None
        target.domain_id = domains.get(row.get("domain") or "")
        target.contract_json = row.get("contract") or {}
        session.commit()
    return {"created": created, "updated": updated, "skipped": skipped,
            "missing_datasource_refs": sorted(set(missing_refs)),
            "unresolved_datasources": unresolved}


def promote_project(session, source_project_id, target_project_id, actor):
    if source_project_id == target_project_id:
        raise ValueError("source and target projects must differ")
    bundle = export_bundle(session, source_project_id)
    report = validate_bundle(session, target_project_id, bundle)
    if report["conflicts"]:
        raise ValueError("bundle conflicts: %s"
                         % ", ".join(report["conflicts"][:5]))
    if report["unresolved_datasources"]:
        raise ValueError("missing datasources: %s"
                         % ", ".join(report["unresolved_datasources"][:5]))
    result = import_bundle(session, target_project_id, bundle, actor)
    return {"source_project_id": source_project_id,
            "target_project_id": target_project_id,
            "validation": report, "import": result}
