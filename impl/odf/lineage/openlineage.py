import json
import uuid
from datetime import datetime, timezone

from odf.models import Asset, AssetVersion, Datasource
from odf.services.platform import get_doc
from odf.settings import get_settings

PRODUCER = "https://github.com/CildCo/weft"
SCHEMA = "https://openlineage.io/spec/2-0-2/OpenLineage.json"


def _config(session):
    return get_doc(session, mask=False).get("lineage") or {}


def _post(session, url, token, payload):
    from odf.services.net import request
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    code, _, _ = request(
        url, method="POST", body=body, headers=headers, timeout=10,
        allow_private=get_settings().http_allow_private,
        max_bytes=1024 * 1024)
    if code >= 400:
        raise ValueError("lineage endpoint answered HTTP %d" % code)


def _dataset(session, namespace, datasource_id, table):
    ds = session.get(Datasource, datasource_id) if datasource_id else None
    name = "%s.%s" % (ds.name if ds else "unknown", table or "")
    return {"namespace": "%s.%s" % (namespace, ds.kind if ds else "data"),
            "name": name}


def _datasets(session, asset, content, namespace):
    out = []
    for node in content.get("nodes") or []:
        if node.get("type") not in ("source", "sink"):
            continue
        config = node.get("config") or {}
        out.append(_dataset(session, namespace,
                            config.get("datasource_id"),
                            config.get("table")))
    return out


def emit(session, event_type, job, error=None):
    try:
        config = _config(session)
        url = (config.get("openlineage_url") or "").strip()
        if not url or not job or not job.asset_id:
            return False
        asset = session.get(Asset, job.asset_id)
        if not asset or asset.type != "pipeline":
            return False
        version_id = asset.published_version_id or asset.draft_version_id
        version = session.get(AssetVersion, version_id) if version_id else None
        content = version.content_json if version else {}
        namespace = (config.get("namespace") or "odf").strip() or "odf"
        datasets = _datasets(session, asset, content, namespace)
        inputs = datasets[:1]
        outputs = datasets[1:] or datasets
        payload = {
            "eventTime": datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"),
            "producer": PRODUCER,
            "schemaURL": SCHEMA,
            "eventType": event_type,
            "run": {
                "runId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                        "odf-job-%s" % job.id)),
                "facets": {
                    "odf": {
                        "_producer": PRODUCER,
                        "_schemaURL": SCHEMA,
                        "jobId": job.id,
                        "projectId": asset.project_id,
                        "attempts": job.attempts,
                    }
                },
            },
            "job": {"namespace": namespace, "name": asset.key,
                    "facets": {}},
            "inputs": inputs,
            "outputs": outputs,
        }
        if error:
            payload["run"]["facets"]["errorMessage"] = {
                "_producer": PRODUCER, "_schemaURL": SCHEMA,
                "message": str(error)[:500],
            }
        _post(session, url, config.get("openlineage_token"), payload)
        return True
    except Exception:
        return False


def send_test(session):
    config = _config(session)
    url = (config.get("openlineage_url") or "").strip()
    if not url:
        raise ValueError("OpenLineage endpoint is not configured")
    payload = {
        "eventTime": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        "producer": PRODUCER,
        "schemaURL": SCHEMA,
        "eventType": "COMPLETE",
        "run": {"runId": str(uuid.uuid4()), "facets": {}},
        "job": {"namespace": config.get("namespace") or "odf",
                "name": "odf-connection-test", "facets": {}},
        "inputs": [],
        "outputs": [],
    }
    _post(session, url, config.get("openlineage_token"), payload)
    return {"ok": True, "message": "OpenLineage test event sent"}
