import { useCallback, useEffect, useRef, useState } from 'react'
import { clearChatSession, getChatHistory, streamChat } from '../api/chat'
import { ApiClientError } from '../api/client'
import type { SourceCitation, UiMessage } from '../types/api'

const SESSION_KEY = 'landchain_session_id'

function createId(): string {
  return crypto.randomUUID()
}

function toUiMessages(
  messages: { role: 'user' | 'assistant'; content: string }[],
): UiMessage[] {
  return messages.map((msg) => ({
    id: createId(),
    role: msg.role,
    content: msg.content,
  }))
}

export function useChat() {
  const [sessionId, setSessionId] = useState<string | null>(() =>
    localStorage.getItem(SESSION_KEY),
  )
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [lastSources, setLastSources] = useState<string[]>([])
  const [lastCitations, setLastCitations] = useState<SourceCitation[]>([])
  const [lastChunksUsed, setLastChunksUsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const historyLoadedRef = useRef(false)

  const persistSession = useCallback((id: string) => {
    setSessionId(id)
    localStorage.setItem(SESSION_KEY, id)
  }, [])

  const loadHistory = useCallback(async (id: string) => {
    setIsLoadingHistory(true)
    setError(null)
    try {
      const history = await getChatHistory(id)
      setMessages(toUiMessages(history.messages))
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 404) {
        localStorage.removeItem(SESSION_KEY)
        setSessionId(null)
        setMessages([])
      } else {
        setError(err instanceof Error ? err.message : '加载历史失败')
      }
    } finally {
      setIsLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    if (historyLoadedRef.current) {
      return
    }
    const stored = localStorage.getItem(SESSION_KEY)
    if (stored) {
      historyLoadedRef.current = true
      void loadHistory(stored)
    }
  }, [loadHistory])

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming) {
        return
      }

      setError(null)
      setIsStreaming(true)

      const userMessage: UiMessage = {
        id: createId(),
        role: 'user',
        content: trimmed,
      }
      const assistantId = createId()
      const assistantMessage: UiMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        streaming: true,
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])

      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamChat(
          { session_id: sessionId ?? undefined, message: trimmed },
          (event) => {
            if (event.event === 'session') {
              persistSession(event.data.session_id)
            } else if (event.event === 'token') {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? { ...msg, content: msg.content + event.data.text }
                    : msg,
                ),
              )
            } else if (event.event === 'done') {
              persistSession(event.data.session_id)
              setLastSources(event.data.sources)
              setLastCitations(event.data.citations ?? [])
              setLastChunksUsed(event.data.chunks_used)
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? {
                        ...msg,
                        streaming: false,
                        sources: event.data.sources,
                        citations: event.data.citations,
                        chunksUsed: event.data.chunks_used,
                      }
                    : msg,
                ),
              )
            } else if (event.event === 'error') {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? {
                        ...msg,
                        content: event.data.message,
                        streaming: false,
                        error: true,
                      }
                    : msg,
                ),
              )
              setError(event.data.message)
            }
          },
          controller.signal,
        )
      } catch (err) {
        if (controller.signal.aborted) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, streaming: false, content: msg.content || '（已停止生成）' }
                : msg,
            ),
          )
        } else {
          const message =
            err instanceof ApiClientError
              ? err.status === 503
                ? 'Ollama 服务不可用，请检查后端与 Ollama 是否已启动'
                : err.message
              : err instanceof Error
                ? err.message
                : '发送失败'
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: message, streaming: false, error: true }
                : msg,
            ),
          )
          setError(message)
        }
      } finally {
        setIsStreaming(false)
        abortRef.current = null
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, streaming: false } : msg,
          ),
        )
      }
    },
    [isStreaming, sessionId, persistSession],
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const newSession = useCallback(() => {
    abortRef.current?.abort()
    localStorage.removeItem(SESSION_KEY)
    historyLoadedRef.current = false
    setSessionId(null)
    setMessages([])
    setLastSources([])
    setLastCitations([])
    setLastChunksUsed(0)
    setError(null)
    setIsStreaming(false)
  }, [])

  const clearSession = useCallback(async () => {
    abortRef.current?.abort()
    if (sessionId) {
      try {
        await clearChatSession(sessionId)
      } catch {
        // ignore clear errors for stale sessions
      }
    }
    newSession()
  }, [sessionId, newSession])

  return {
    sessionId,
    messages,
    isStreaming,
    isLoadingHistory,
    lastSources,
    lastCitations,
    lastChunksUsed,
    error,
    sendMessage,
    stopStreaming,
    newSession,
    clearSession,
  }
}
