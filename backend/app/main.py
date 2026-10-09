"""AuditFlow AI - Reconcile. Investigate. Resolve.  (FastAPI application)"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (routes_anomalies, routes_health, routes_investigation, routes_reconciliation, routes_reports,
                     routes_transactions, routes_upload)
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging_config import setup_logging
from app.database.database import init_db
from app.llm.ollama_client import get_ollama_client
from app.parsers.transaction_parser import ParseError

log = logging.getLogger("auditflow")


def _err(status: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def create_app() -> FastAPI:
    s = get_settings()
    setup_logging(s.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        for d in (s.upload_dir, s.reports_dir):
            Path(d).mkdir(parents=True, exist_ok=True)
        init_db()
        log.info("%s v%s started - %s", s.app_name, s.version, s.tagline)
        log.info("Ollama: %s", "available" if get_ollama_client().is_available() else "unavailable (deterministic fallback active)")
        yield

    app = FastAPI(title=s.app_name, version=s.version, lifespan=lifespan,
                  description=f"**{s.app_name}** - {s.tagline}  AI-powered bank reconciliation & anomaly investigation.")
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
                       allow_credentials=origins != ["*"])

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _err(exc.status_code, exc.code, exc.message)

    @app.exception_handler(ParseError)
    async def _parse_error(_: Request, exc: ParseError):
        return _err(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e.get("loc", ())), "message": e.get("msg", "")} for e in exc.errors()]
        return _err(422, "VALIDATION_ERROR", "Request validation failed.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _err(exc.status_code, "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def _db(_: Request, exc: SQLAlchemyError):
        log.error("Database error: %s", type(exc).__name__)
        return _err(500, "DATABASE_ERROR", "A database error occurred.")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return _err(500, "INTERNAL_ERROR", "An unexpected error occurred.")

    for r in (routes_health, routes_upload, routes_reconciliation, routes_transactions, routes_anomalies,
              routes_investigation, routes_reports):
        app.include_router(r.router)

    @app.get("/", include_in_schema=False)
    def root():
        return {"service": s.app_name, "tagline": s.tagline, "version": s.version, "docs": "/docs", "health": "/health"}

    return app


app = create_app()
