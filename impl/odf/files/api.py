from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.files import service
from odf.services.auth import require_editor, require_user

router = APIRouter()


def _value(e):
    msg = str(e)
    return HTTPException(404 if "not found" in msg else 400, msg)


@router.get("/files")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return service.list_files(s, claims["project_id"])


@router.post("/files")
def upload(file: UploadFile = File(...),
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    try:
        return service.store_stream(s, claims["project_id"], file.filename,
                                    file.content_type, file.file,
                                    claims["sub"])
    except ValueError as e:
        raise _value(e)


@router.get("/files/{file_id}/download")
def download(file_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    try:
        f, chunks = service.open_file(s, claims["project_id"], file_id)
    except ValueError as e:
        raise _value(e)
    from urllib.parse import quote
    headers = {"Content-Disposition":
               "attachment; filename*=UTF-8''%s" % quote(f.name)}
    return StreamingResponse(
        chunks, media_type=f.content_type or "application/octet-stream",
        headers=headers)


@router.delete("/files/{file_id}")
def delete(file_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        return service.delete_file(s, claims["project_id"], file_id,
                                   claims["sub"])
    except ValueError as e:
        raise _value(e)
