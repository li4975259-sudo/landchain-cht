import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    SessionClearResponse,
)
from app.services.ollama_client import check_ollama_health
from app.utils.async_bridge import iter_sync_in_thread, run_sync

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


async def _ensure_ollama(request: Request) -> None:
    if not await check_ollama_health(request.app.state.settings):
        raise HTTPException(status_code=503, detail="Ollama service is unavailable")


def _resolve_session_id(session_id: str | None) -> str:
    return session_id or str(uuid.uuid4())


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    request_id = getattr(request.state, "request_id", "-")
    await _ensure_ollama(request)

    session_id = _resolve_session_id(body.session_id)
    chat_service = request.app.state.chat_service
    try:
        result = await run_sync(chat_service.chat, session_id, body.message, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc

    logger.info(
        "http.chat.complete request_id=%s session_id=%s mode=%s chunks=%s total_ms=%s",
        request_id,
        session_id,
        result.get("mode"),
        result.get("chunks_used"),
        int((time.perf_counter() - start) * 1000),
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    request_start = time.perf_counter()
    request_id = getattr(request.state, "request_id", "-")
    await _ensure_ollama(request)

    session_id = _resolve_session_id(body.session_id)
    chat_service = request.app.state.chat_service

    async def event_generator() -> AsyncIterator[str]:
        try:
            yield _sse_event("session", {"session_id": session_id})
            token_stream, sources, citations, chunks_used, mode = await run_sync(
                chat_service.stream,
                session_id,
                body.message,
                top_k=body.top_k,
            )
            async for token in iter_sync_in_thread(token_stream):
                if token:
                    yield _sse_event("token", {"text": token})
            yield _sse_event(
                "done",
                {
                    "session_id": session_id,
                    "sources": sources,
                    "citations": citations,
                    "chunks_used": chunks_used,
                    "mode": mode,
                },
            )
            logger.info(
                "http.chat_stream.complete request_id=%s session_id=%s mode=%s chunks=%s total_ms=%s",
                request_id,
                session_id,
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


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str, request: Request) -> ChatHistoryResponse:
    chat_service = request.app.state.chat_service
    messages = await run_sync(chat_service.get_history, session_id)
    return ChatHistoryResponse(session_id=session_id, messages=messages)


@router.delete("/sessions/{session_id}", response_model=SessionClearResponse)
async def clear_chat_session(session_id: str, request: Request) -> SessionClearResponse:
    chat_service = request.app.state.chat_service
    await run_sync(chat_service.clear_session, session_id)
    return SessionClearResponse(session_id=session_id, cleared=True)
