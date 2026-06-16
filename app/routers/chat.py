import json
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

router = APIRouter(prefix="/chat", tags=["chat"])


async def _ensure_ollama(request: Request) -> None:
    if not await check_ollama_health(request.app.state.settings):
        raise HTTPException(status_code=503, detail="Ollama service is unavailable")


def _resolve_session_id(session_id: str | None) -> str:
    return session_id or str(uuid.uuid4())


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    await _ensure_ollama(request)

    session_id = _resolve_session_id(body.session_id)
    chat_service = request.app.state.chat_service
    try:
        result = chat_service.chat(session_id, body.message, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc

    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    await _ensure_ollama(request)

    session_id = _resolve_session_id(body.session_id)
    chat_service = request.app.state.chat_service

    async def event_generator() -> AsyncIterator[str]:
        try:
            yield _sse_event("session", {"session_id": session_id})
            token_stream, sources, citations, chunks_used, mode = chat_service.stream(
                session_id,
                body.message,
                top_k=body.top_k,
            )
            for token in token_stream:
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
    messages = chat_service.get_history(session_id)
    return ChatHistoryResponse(session_id=session_id, messages=messages)


@router.delete("/sessions/{session_id}", response_model=SessionClearResponse)
async def clear_chat_session(session_id: str, request: Request) -> SessionClearResponse:
    chat_service = request.app.state.chat_service
    chat_service.clear_session(session_id)
    return SessionClearResponse(session_id=session_id, cleared=True)
