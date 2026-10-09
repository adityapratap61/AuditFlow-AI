"""Anomaly queries and aggregate helpers."""
from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.database import models as m
from app.database.schemas import AnomalyDetail
from app.domain import ANOMALY_TYPES

SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def count_by_type(types: Iterable[str]) -> dict:
    c = Counter(types)
    return {t: c.get(t, 0) for t in ANOMALY_TYPES}


def list_anomalies(db: Session, *, run_id: Optional[str] = None, anomaly_type: Optional[str] = None,
                   severity: Optional[str] = None, status: Optional[str] = None, source: Optional[str] = None,
                   limit: int = 50, offset: int = 0) -> Tuple[List[m.Anomaly], int]:
    A = m.Anomaly
    conds = []
    for col, val in ((A.run_id, run_id), (A.anomaly_type, anomaly_type and anomaly_type.upper()),
                     (A.severity, severity and severity.upper()), (A.status, status and status.upper()),
                     (A.source, source and source.upper())):
        if val:
            conds.append(col == val)
    total = db.scalar(select(func.count()).select_from(A).where(*conds)) or 0
    rows = list(db.scalars(select(A).where(*conds)).all())
    rows.sort(key=lambda a: (SEVERITY_RANK.get(a.severity, 3), a.anomaly_type, a.created_at))
    return rows[offset:offset + limit], int(total)


def get_anomaly_detail(db: Session, anomaly_id: str) -> AnomalyDetail:
    a = db.get(m.Anomaly, anomaly_id)
    if a is None:
        raise AppError(404, "ANOMALY_NOT_FOUND", "Anomaly not found.")
    return AnomalyDetail.model_validate(a)
