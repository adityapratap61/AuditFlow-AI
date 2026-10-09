from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.database.database import check_db
from app.database.schemas import HealthResponse
from app.llm.ollama_client import get_ollama_client

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health (Ollama is optional)")
def health(response: Response) -> HealthResponse:
    db_ok = check_db()
    ollama_ok = get_ollama_client().is_available()
    if not db_ok:
        response.status_code = 503
    return HealthResponse(status="healthy" if db_ok else "unhealthy", database="connected" if db_ok else "disconnected",
                          ollama="available" if ollama_ok else "unavailable", version=get_settings().version)
