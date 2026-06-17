import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentHistoryResponse,
    AgentRunsResponse,
    AgentToolsResponse,
    ApprovalActionRequest,
    ApprovalResponse,
    PendingApprovalsResponse,
    SessionClearResponse,
)
from app.services.ollama_client import check_ollama_health

router = APIRouter(prefix="/agent", tags=["agent"])


def _resolve_session_id(session_id: str | None) -> str:
    return session_id or str(uuid.uuid4())


def _check_agent_auth(request: Request, x_agent_key: str | None) -> None:
    settings = request.app.state.settings
    if settings.agent_require_api_key and not settings.agent_api_key:
        raise HTTPException(
            status_code=503,
            detail="Agent API key is not configured",
        )
    if settings.agent_api_key and x_agent_key != settings.agent_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Agent-Key")


def _resolve_actor(resolved_by: str | None) -> str:
    actor = (resolved_by or "user").strip()
    return actor or "user"


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _ensure_agent(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.agent_enabled:
        raise HTTPException(status_code=503, detail="Agent is disabled")
    if not await check_ollama_health(settings):
        raise HTTPException(status_code=503, detail="Ollama service is unavailable")


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: Request,
    body: AgentChatRequest,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> AgentChatResponse:
    _check_agent_auth(request, x_agent_key)
    await _ensure_agent(request)
    session_id = _resolve_session_id(body.session_id)
    agent_service = request.app.state.agent_service
    try:
        result = agent_service.chat(session_id, body.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent chat failed: {exc}") from exc
    return AgentChatResponse(**result)


@router.post("/chat/stream")
async def agent_chat_stream(
    request: Request,
    body: AgentChatRequest,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> StreamingResponse:
    _check_agent_auth(request, x_agent_key)
    await _ensure_agent(request)
    session_id = _resolve_session_id(body.session_id)
    agent_service = request.app.state.agent_service

    async def event_generator() -> AsyncIterator[str]:
        try:
            run_id, events, _pending = agent_service.stream(session_id, body.message)
            yield _sse_event("session", {"session_id": session_id, "run_id": run_id})
            for item in events:
                yield _sse_event(item["event"], item["data"])
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/sessions/{session_id}/history", response_model=AgentHistoryResponse)
async def agent_history(
    request: Request,
    session_id: str,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> AgentHistoryResponse:
    _check_agent_auth(request, x_agent_key)
    agent_service = request.app.state.agent_service
    return AgentHistoryResponse(session_id=session_id, messages=agent_service.get_history(session_id))


@router.delete("/sessions/{session_id}", response_model=SessionClearResponse)
async def agent_clear_session(
    request: Request,
    session_id: str,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> SessionClearResponse:
    _check_agent_auth(request, x_agent_key)
    request.app.state.agent_service.clear_session(session_id)
    return SessionClearResponse(session_id=session_id, cleared=True)


@router.get("/sessions/{session_id}/runs", response_model=AgentRunsResponse)
async def agent_runs(
    request: Request,
    session_id: str,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> AgentRunsResponse:
    _check_agent_auth(request, x_agent_key)
    runs = request.app.state.agent_service.list_runs(session_id)
    return AgentRunsResponse(session_id=session_id, runs=runs)


@router.get("/approvals/pending", response_model=PendingApprovalsResponse)
async def pending_approvals(
    request: Request,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> PendingApprovalsResponse:
    _check_agent_auth(request, x_agent_key)
    approvals = request.app.state.agent_service.list_pending_approvals()
    return PendingApprovalsResponse(approvals=approvals)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_shell(
    request: Request,
    approval_id: str,
    body: ApprovalActionRequest,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> ApprovalResponse:
    _check_agent_auth(request, x_agent_key)
    result = request.app.state.agent_service.approve_shell(
        approval_id,
        approved=True,
        resolved_by=_resolve_actor(body.resolved_by),
    )
    return ApprovalResponse(
        status=result["status"],
        approval_id=approval_id,
        result=result.get("result"),
    )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_shell(
    request: Request,
    approval_id: str,
    body: ApprovalActionRequest,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> ApprovalResponse:
    _check_agent_auth(request, x_agent_key)
    result = request.app.state.agent_service.approve_shell(
        approval_id,
        approved=False,
        resolved_by=_resolve_actor(body.resolved_by),
    )
    return ApprovalResponse(status=result["status"], approval_id=approval_id)


@router.get("/tools", response_model=AgentToolsResponse)
async def list_tools(
    request: Request,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> AgentToolsResponse:
    _check_agent_auth(request, x_agent_key)
    tasks = request.app.state.agent_service.task_registry.list_tasks()
    return AgentToolsResponse(tools=tasks)
