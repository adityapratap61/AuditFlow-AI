from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import AnomalyDetail, AnomalyOut, Page
from app.services import anomaly_service as svc

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("", response_model=Page[AnomalyOut], summary="List/filter anomalies (highest severity first)")
def list_anomalies(run_id: Optional[str] = None, anomaly_type: Optional[str] = None,
                   severity: Optional[str] = Query(None, description="HIGH | MEDIUM | LOW"),
                   status: Optional[str] = Query(None, description="OPEN | INVESTIGATED"),
                   source: Optional[str] = Query(None, description="BANK | ACCOUNTING"),
                   limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows, total = svc.list_anomalies(db, run_id=run_id, anomaly_type=anomaly_type, severity=severity, status=status,
                                     source=source, limit=limit, offset=offset)
    return Page[AnomalyOut](items=[AnomalyOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{anomaly_id}", response_model=AnomalyDetail, summary="Anomaly with related transactions")
def get_anomaly(anomaly_id: str, db: Session = Depends(get_db)):
    return svc.get_anomaly_detail(db, anomaly_id)
