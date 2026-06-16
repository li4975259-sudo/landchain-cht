import { apiFetch, apiFetchRaw } from './client'
import { consumeSseStream } from './sse'
import type {
  ChatHistoryResponse,
  ChatRequest,
  ChatStreamEvent,
  SessionClearResponse,
} from '../types/api'

export async function streamChat(
  body: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetchRaw('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  await consumeSseStream(response, onEvent, signal)
}

export async function getChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  return apiFetch<ChatHistoryResponse>(`/chat/sessions/${encodeURIComponent(sessionId)}/history`)
}

export async function clearChatSession(sessionId: string): Promise<SessionClearResponse> {
  return apiFetch<SessionClearResponse>(`/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}
