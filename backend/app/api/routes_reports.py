from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import report_service as svc

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/report/{run_id}", summary="Reconciliation report (JSON by default, CSV with ?format=csv)")
def get_report(run_id: str, format: Literal["json", "csv"] = Query("json"), db: Session = Depends(get_db)):
    if format == "csv":
        return Response(content=svc.build_report_csv(db, run_id), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="auditflow_report_{run_id}.csv"'})
    return svc.build_report(db, run_id)
