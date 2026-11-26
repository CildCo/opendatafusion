from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_user
from odf.services.favorites import (add_favorite, is_favorite,
                                    list_favorites, remove_favorite)

router = APIRouter()


class FavoriteIn(BaseModel):
    object_type: str
    object_id: int


@router.get("/favorites")
def favorites(object_type: str | None = None,
              s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    return list_favorites(s, claims["project_id"], int(claims["sub"]),
                          object_type)


@router.get("/favorites/check")
def check(object_type: str, object_id: int,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return {"favorite": is_favorite(s, claims["project_id"],
                                    int(claims["sub"]), object_type,
                                    object_id)}


@router.post("/favorites", status_code=201)
def create(body: FavoriteIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    try:
        return add_favorite(s, claims["project_id"], int(claims["sub"]),
                            body.object_type, body.object_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/favorites/{object_type}/{object_id}")
def remove(object_type: str, object_id: int,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    return {"removed": remove_favorite(s, claims["project_id"],
                                       int(claims["sub"]), object_type,
                                       object_id)}
