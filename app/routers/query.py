import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import QueryRequest, QueryResponse
from app.services.ollama_client import check_ollama_health
from app.utils.async_bridge import iter_sync_in_thread, run_sync

router = APIRouter(tags=["query"])
logger = logging.getLogger(__name__)


async def _ensure_ollama(request: Request) -> None:
    if not await check_ollama_health(request.app.state.settings):
        raise HTTPException(status_code=503, detail="Ollama service is unavailable")


@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    start = time.perf_counter()
    request_id = getattr(request.state, "request_id", "-")
    await _ensure_ollama(request)

    rag_service = request.app.state.rag_service
    try:
        result = await run_sync(rag_service.query, body.question, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc

    logger.info(
        "http.query.complete request_id=%s mode=%s chunks=%s total_ms=%s",
        request_id,
        result.get("mode"),
        result.get("chunks_used"),
        int((time.perf_counter() - start) * 1000),
    )
    return QueryResponse(**result)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/query/stream")
async def query_stream(request: Request, body: QueryRequest) -> StreamingResponse:
    request_start = time.perf_counter()
    request_id = getattr(request.state, "request_id", "-")
    await _ensure_ollama(request)

    rag_service = request.app.state.rag_service

    async def event_generator() -> AsyncIterator[str]:
        try:
            token_stream, sources, citations, chunks_used, mode = await run_sync(
                rag_service.stream,
                body.question,
                top_k=body.top_k,
            )
            async for token in iter_sync_in_thread(token_stream):
                if token:
                    yield _sse_event("token", {"text": token})
            yield _sse_event(
                "done",
                {
                    "sources": sources,
                    "citations": [c.model_dump() for c in citations],
                    "chunks_used": chunks_used,
                    "mode": mode,
                },
            )
            logger.info(
                "http.query_stream.complete request_id=%s mode=%s chunks=%s total_ms=%s",
                request_id,
                mode,
                chunks_used,
                int((time.perf_counter() - request_start) * 1000),
            )
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
