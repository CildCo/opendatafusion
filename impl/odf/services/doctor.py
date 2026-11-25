import gzip
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, text

from odf.models import (Alert, Asset, Datasource, Job, Project, QueryRun,
                        User)
from odf.settings import get_settings


def _revisions():
    current = head = None
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from odf.db import engine
        root = Path(__file__).resolve().parents[2]
        config_path = root / "alembic.ini"
        if config_path.exists():
            head = ScriptDirectory.from_config(
                Config(str(config_path))).get_current_head()
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except Exception:
        return {"current": current, "head": head, "pending": None}
    return {"current": current, "head": head,
            "pending": bool(head and current != head)}


def _counts(session):
    jobs = {status: count for status, count in
            session.query(Job.status, func.count(Job.id))
            .group_by(Job.status).all()}
    assets = {kind: count for kind, count in
              session.query(Asset.type, func.count(Asset.id))
              .group_by(Asset.type).all()}
    return {
        "projects": session.query(func.count(Project.id)).scalar() or 0,
        "users": session.query(func.count(User.id)).scalar() or 0,
        "datasources": session.query(func.count(Datasource.id)).scalar() or 0,
        "assets": assets,
        "jobs": jobs,
        "open_alerts": session.query(func.count(Alert.id))
        .filter(Alert.status != "closed").scalar() or 0,
        "query_runs": session.query(func.count(QueryRun.id)).scalar() or 0,
    }


def _disk():
    settings = get_settings()
    path = settings.file_dir or "."
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {"path": path, "free_mb": None, "total_mb": None}
    return {"path": path,
            "free_mb": round(usage.free / 1048576),
            "total_mb": round(usage.total / 1048576)}


def check(session):
    settings = get_settings()
    database = {"dialect": None, "reachable": False}
    try:
        database["dialect"] = session.bind.dialect.name
        session.execute(text("select 1"))
        database["reachable"] = True
    except Exception:
        database["reachable"] = False
    revisions = _revisions()
    disk = _disk()
    counts = _counts(session)
    ok = bool(database["reachable"]) and revisions.get("pending") is not True
    if disk.get("free_mb") is not None and disk["free_mb"] < 512:
        ok = False
    return {
        "ok": ok,
        "database": database,
        "migrations": revisions,
        "counts": counts,
        "disk": disk,
        "retention_days": {
            key: getattr(settings, "retention_%s_days" % key)
            for key in ("query_run", "job", "notification", "alert",
                        "webhook_delivery", "contract_check")},
        "generated_at": datetime.now(timezone.utc),
    }


def check_backup(path):
    target = Path(path)
    result = {"path": str(target), "ok": False, "size_mb": 0,
              "kind": "unknown", "detail": ""}
    if not target.exists() or not target.is_file():
        result["detail"] = "file not found"
        return result
    result["size_mb"] = round(target.stat().st_size / 1048576, 2)
    if target.stat().st_size == 0:
        result["detail"] = "empty file"
        return result
    name = target.name.lower()
    try:
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            result["kind"] = "tar.gz"
            with tarfile.open(target, "r:gz") as archive:
                names = archive.getnames()
            result["ok"] = bool(names)
            result["detail"] = "%d entries" % len(names)
        elif name.endswith(".gz"):
            result["kind"] = "gzip"
            with gzip.open(target, "rb") as handle:
                head = handle.read(4096)
            result["ok"] = bool(head)
            result["detail"] = "gzip readable"
        else:
            result["kind"] = "plain"
            raw = target.read_bytes()[:65536]
            text = raw.decode("utf-8", "ignore")
            result["ok"] = ("CREATE TABLE" in text.upper()
                            or "COPY " in text.upper()
                            or text.startswith("--"))
            result["detail"] = "SQL text detected" if result["ok"] \
                else "no SQL statements found"
    except Exception as error:
        result["detail"] = type(error).__name__
    return result


def dump(session):
    return json.dumps(check(session), default=str, indent=2)
