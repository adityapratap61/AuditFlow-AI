from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import InvestigateRequest, InvestigationOut
from app.services import investigation_service as svc

router = APIRouter(prefix="/api", tags=["investigation"])


@router.post("/investigate/{anomaly_id}", response_model=InvestigationOut,
             summary="Run the investigation agent on one anomaly (stores the step trail)")
def investigate(anomaly_id: str, body: Optional[InvestigateRequest] = Body(None), db: Session = Depends(get_db)):
    return svc.investigate_anomaly(db, anomaly_id, use_llm=body.use_llm if body else True)


@router.get("/investigations/{investigation_id}", response_model=InvestigationOut, summary="Investigation with steps")
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    return svc.get_investigation(db, investigation_id)


@router.get("/investigations", response_model=List[InvestigationOut], summary="List investigations")
def list_investigations(run_id: Optional[str] = None, anomaly_id: Optional[str] = None,
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return svc.list_investigations(db, run_id, anomaly_id, limit, offset)
