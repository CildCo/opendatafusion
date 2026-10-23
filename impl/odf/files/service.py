import hashlib
import io
import os
import tempfile

from odf.files.storage import storage_for
from odf.models import FileObject
from odf.services.audit import write_audit
from odf.settings import get_settings


def safe_name(name):
    name = os.path.basename(str(name or "file")).replace("\x00", "")
    name = "".join(c for c in name if ord(c) >= 32)
    if not name or name in (".", ".."):
        name = "file"
    return name[:256]


def _max_bytes():
    return get_settings().file_max_mb * 1024 * 1024


def _out(f):
    return {"id": f.id, "name": f.name, "content_type": f.content_type,
            "size": f.size, "sha256": f.sha256, "created_by": f.created_by,
            "created_at": f.created_at}


def store_stream(session, project_id, name, content_type, file_obj, actor):
    limit = _max_bytes()
    storage = storage_for(get_settings())
    digest = hashlib.sha256()
    size = 0
    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError("file exceeds size limit")
            digest.update(chunk)
            tmp.write(chunk)
        tmp.close()
        sha = digest.hexdigest()
        key = "%s/%s/%s" % (project_id, sha[:2], sha)
        if not storage.exists(key):
            storage.put(key, tmp.name)
        row = FileObject(project_id=project_id, name=safe_name(name),
                         content_type=(content_type or
                                       "application/octet-stream")[:128],
                         size=size, sha256=sha, storage_key=key,
                         created_by=actor)
        session.add(row)
        session.commit()
        session.refresh(row)
        if not storage.exists(key):
            storage.put(key, tmp.name)
        write_audit(session, actor, "upload_file", str(row.id),
                    {"name": row.name, "size": row.size})
        return _out(row)
    finally:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def store_bytes(session, project_id, name, content_type, data, actor):
    return store_stream(session, project_id, name, content_type,
                        io.BytesIO(data), actor)


def list_files(session, project_id):
    return [_out(f) for f in session.query(FileObject)
            .filter_by(project_id=project_id)
            .order_by(FileObject.id.desc()).all()]


def get_file(session, project_id, file_id):
    f = session.get(FileObject, file_id)
    if not f or f.project_id != project_id:
        raise ValueError("file not found")
    if not storage_for(get_settings()).exists(f.storage_key):
        raise ValueError("file not found")
    return f


def open_file(session, project_id, file_id):
    f = get_file(session, project_id, file_id)
    return f, storage_for(get_settings()).open(f.storage_key)


def delete_file(session, project_id, file_id, actor):
    f = session.get(FileObject, file_id)
    if not f or f.project_id != project_id:
        raise ValueError("file not found")
    key = f.storage_key
    session.delete(f)
    session.commit()
    if session.query(FileObject).filter_by(storage_key=key).count() == 0:
        storage_for(get_settings()).delete(key)
    write_audit(session, actor, "delete_file", str(file_id), {})
    return {"deleted": True}
