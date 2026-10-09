import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.database import get_db
from app.database.schemas import UploadResponse
from app.domain import ACCOUNTING, BANK
from app.parsers.csv_parser import parse_csv
from app.parsers.pdf_parser import parse_pdf
from app.services import reconciliation_service as svc
from app.utils.text import safe_filename

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["upload"])
ALLOWED = {BANK: {".csv", ".pdf"}, ACCOUNTING: {".csv"}}


def _save_copy(content: bytes, filename: str) -> None:
    """Keep an audit copy under uploads/ (never executed, random prefix, no user-controlled path)."""
    try:
        base = Path(get_settings().upload_dir).resolve()
        base.mkdir(parents=True, exist_ok=True)
        target = (base / f"{uuid.uuid4().hex[:12]}_{filename}").resolve()
        if base in target.parents:
            target.write_bytes(content)
    except OSError as exc:
        log.warning("Could not store upload copy (%s)", type(exc).__name__)


def _handle(db: Session, source: str, file: UploadFile, run_id: Optional[str]) -> UploadResponse:
    s = get_settings()
    filename = safe_filename(file.filename or "upload")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED[source]:
        raise AppError(415, "UNSUPPORTED_FILE_TYPE",
                       f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(ALLOWED[source]))}.")
    limit = s.max_upload_mb * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise AppError(413, "FILE_TOO_LARGE", f"File exceeds the {s.max_upload_mb} MB limit.")
    log.info("Upload received source=%s type=%s bytes=%d", source, ext, len(content))
    result = parse_pdf(content, source) if ext == ".pdf" else parse_csv(content, source)  # ParseError -> JSON error
    _save_copy(content, filename)
    return svc.store_upload(db, run_id or None, source, result, filename, ext.lstrip("."))


@router.post("/bank", response_model=UploadResponse, summary="Upload a bank statement (CSV or text PDF)")
def upload_bank(file: UploadFile = File(...), run_id: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return _handle(db, BANK, file, run_id)


@router.post("/accounting", response_model=UploadResponse, summary="Upload an accounting export (CSV)")
def upload_accounting(file: UploadFile = File(...), run_id: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return _handle(db, ACCOUNTING, file, run_id)
