from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse
from app.services.ollama_client import check_ollama_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    vectorstore = request.app.state.vectorstore
    business_store = request.app.state.business_store

    ollama_reachable = await check_ollama_health(settings)
    qdrant_reachable = vectorstore.ping()
    postgres_reachable = business_store.ping()

    overall_ok = ollama_reachable and qdrant_reachable and postgres_reachable

    return HealthResponse(
        status="ok" if overall_ok else "degraded",
        ollama_reachable=ollama_reachable,
        qdrant_reachable=qdrant_reachable,
        chunk_count=vectorstore.count(),
        chat_model=settings.ollama_chat_model,
        embed_model=settings.embed_model,
        rerank_enabled=settings.rerank_enabled,
        rerank_model=settings.rerank_model,
        postgres_reachable=postgres_reachable,
        agent_enabled=settings.agent_enabled,
        agent_model=settings.effective_agent_model if settings.agent_enabled else None,
    )
