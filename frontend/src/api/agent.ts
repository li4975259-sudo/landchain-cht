import { apiFetch, apiFetchRaw } from './client'
import { consumeAgentSseStream } from './sse'
import type {
  AgentChatRequest,
  AgentHistoryResponse,
  AgentStreamEvent,
  ApprovalResponse,
  PendingApprovalsResponse,
  SessionClearResponse,
} from '../types/api'

export async function streamAgent(
  body: AgentChatRequest,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetchRaw('/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  await consumeAgentSseStream(response, onEvent, signal)
}

export async function getAgentHistory(sessionId: string): Promise<AgentHistoryResponse> {
  return apiFetch<AgentHistoryResponse>(`/agent/sessions/${encodeURIComponent(sessionId)}/history`)
}

export async function clearAgentSession(sessionId: string): Promise<SessionClearResponse> {
  return apiFetch<SessionClearResponse>(`/agent/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}

export async function getPendingApprovals(): Promise<PendingApprovalsResponse> {
  return apiFetch<PendingApprovalsResponse>('/agent/approvals/pending')
}

export async function approveShell(approvalId: string): Promise<ApprovalResponse> {
  return apiFetch<ApprovalResponse>(`/agent/approvals/${encodeURIComponent(approvalId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolved_by: 'user' }),
  })
}

export async function rejectShell(approvalId: string): Promise<ApprovalResponse> {
  return apiFetch<ApprovalResponse>(`/agent/approvals/${encodeURIComponent(approvalId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolved_by: 'user' }),
  })
}
