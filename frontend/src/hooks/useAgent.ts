import { useCallback, useEffect, useRef, useState } from 'react'
import {
  approveShell,
  clearAgentSession,
  getAgentHistory,
  rejectShell,
  streamAgent,
} from '../api/agent'
import { ApiClientError } from '../api/client'
import type { AgentUiMessage, ApprovalRequest, ToolStep } from '../types/api'

const SESSION_KEY = 'landchain_agent_session_id'

function createId(): string {
  return crypto.randomUUID()
}

export function useAgent() {
  const [sessionId, setSessionId] = useState<string | null>(() =>
    localStorage.getItem(SESSION_KEY),
  )
  const [messages, setMessages] = useState<AgentUiMessage[]>([])
  const [toolSteps, setToolSteps] = useState<ToolStep[]>([])
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const persistSession = useCallback((id: string) => {
    setSessionId(id)
    localStorage.setItem(SESSION_KEY, id)
  }, [])

  const loadHistory = useCallback(async (id: string) => {
    setIsLoadingHistory(true)
    setError(null)
    try {
      const history = await getAgentHistory(id)
      setMessages(
        history.messages.map((msg) => ({
          id: createId(),
          role: msg.role,
          content: msg.content,
        })),
      )
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
    const stored = localStorage.getItem(SESSION_KEY)
    if (stored) {
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
      setToolSteps([])
      setPendingApproval(null)

      const userMessage: AgentUiMessage = {
        id: createId(),
        role: 'user',
        content: trimmed,
      }
      const assistantId = createId()
      const assistantMessage: AgentUiMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        streaming: true,
        toolSteps: [],
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])

      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamAgent(
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
            } else if (event.event === 'tool_start') {
              const step: ToolStep = {
                tool: event.data.tool,
                input: event.data.input,
                status: 'running',
              }
              setToolSteps((prev) => [...prev, step])
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? { ...msg, toolSteps: [...(msg.toolSteps ?? []), step] }
                    : msg,
                ),
              )
            } else if (event.event === 'tool_end') {
              setToolSteps((prev) =>
                prev.map((s) =>
                  s.tool === event.data.tool && s.status === 'running'
                    ? { ...s, status: 'done' }
                    : s,
                ),
              )
            } else if (event.event === 'approval_required') {
              setPendingApproval(event.data)
            } else if (event.event === 'done') {
              persistSession(event.data.session_id)
              if (event.data.pending_approval) {
                setPendingApproval(event.data.pending_approval)
              }
            } else if (event.event === 'error') {
              setError(event.data.message)
            }
          },
          controller.signal,
        )
      } catch (err) {
        if (!controller.signal.aborted) {
          const message =
            err instanceof ApiClientError ? err.message : err instanceof Error ? err.message : '发送失败'
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

  const handleApprove = useCallback(async () => {
    if (!pendingApproval) return
    try {
      await approveShell(pendingApproval.approval_id)
      setPendingApproval(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批失败')
    }
  }, [pendingApproval])

  const handleReject = useCallback(async () => {
    if (!pendingApproval) return
    try {
      await rejectShell(pendingApproval.approval_id)
      setPendingApproval(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '拒绝失败')
    }
  }, [pendingApproval])

  const newSession = useCallback(() => {
    abortRef.current?.abort()
    localStorage.removeItem(SESSION_KEY)
    setSessionId(null)
    setMessages([])
    setToolSteps([])
    setPendingApproval(null)
    setError(null)
  }, [])

  const clearSession = useCallback(async () => {
    abortRef.current?.abort()
    if (sessionId) {
      try {
        await clearAgentSession(sessionId)
      } catch {
        // ignore
      }
    }
    newSession()
  }, [sessionId, newSession])

  return {
    sessionId,
    messages,
    toolSteps,
    pendingApproval,
    isStreaming,
    isLoadingHistory,
    error,
    sendMessage,
    handleApprove,
    handleReject,
    newSession,
    clearSession,
  }
}
