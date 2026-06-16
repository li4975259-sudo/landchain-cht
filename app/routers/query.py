import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import QueryRequest, QueryResponse
from app.services.ollama_client import check_ollama_health

router = APIRouter(tags=["query"])


async def _ensure_ollama(request: Request) -> None:
    if not await check_ollama_health(request.app.state.settings):
        raise HTTPException(status_code=503, detail="Ollama service is unavailable")


@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    await _ensure_ollama(request)

    rag_service = request.app.state.rag_service
    try:
        result = rag_service.query(body.question, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc

    return QueryResponse(**result)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/query/stream")
async def query_stream(request: Request, body: QueryRequest) -> StreamingResponse:
    await _ensure_ollama(request)

    rag_service = request.app.state.rag_service

    async def event_generator() -> AsyncIterator[str]:
        try:
            token_stream, sources, citations, chunks_used, mode = rag_service.stream(
                body.question,
                top_k=body.top_k,
            )
            for token in token_stream:
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
