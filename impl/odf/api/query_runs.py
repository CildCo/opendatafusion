from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_editor
from odf.services.query_log import get_run, list_runs, summary

router = APIRouter()


@router.get("/query-runs")
def runs(page: int = 1, page_size: int = 50, datasource_id: int | None = None,
         status: str | None = None, source: str | None = None,
         s: Session = Depends(get_session),
         claims: dict = Depends(require_editor)):
    return list_runs(s, claims["project_id"], datasource_id=datasource_id,
                     status=status, source=source, page=page,
                     page_size=page_size)


@router.get("/query-runs/summary")
def summary_(days: int = 7, s: Session = Depends(get_session),
             claims: dict = Depends(require_editor)):
    return summary(s, claims["project_id"], days)


@router.get("/query-runs/{run_id}")
def run_detail(run_id: int, s: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    try:
        return get_run(s, claims["project_id"], run_id)
    except ValueError:
        raise HTTPException(404, "query run not found")
