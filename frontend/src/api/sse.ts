import type { AgentStreamEvent, ChatStreamEvent, SourceCitation } from '../types/api'

function parseSseBlock(block: string): ChatStreamEvent | null {
  const lines = block.split('\n').filter(Boolean)
  let event = 'message'
  let data = ''

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      data = line.slice(5).trim()
    }
  }

  if (!data) {
    return null
  }

  try {
    const parsed = JSON.parse(data) as Record<string, unknown>
    switch (event) {
      case 'session':
        return { event: 'session', data: parsed as { session_id: string } }
      case 'token':
        return { event: 'token', data: parsed as { text: string } }
      case 'done':
        return {
          event: 'done',
          data: parsed as {
            session_id: string
            sources: string[]
            citations?: SourceCitation[]
            chunks_used: number
          },
        }
      case 'error':
        return { event: 'error', data: parsed as { message: string } }
      default:
        return null
    }
  } catch {
    return null
  }
}

export async function consumeSseStream(
  response: Response,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('响应不支持流式读取')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel()
        return
      }

      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() ?? ''

      for (const block of blocks) {
        const event = parseSseBlock(block.trim())
        if (event) {
          onEvent(event)
        }
      }
    }

    if (buffer.trim()) {
      const event = parseSseBlock(buffer.trim())
      if (event) {
        onEvent(event)
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseAgentSseBlock(block: string): AgentStreamEvent | null {
  const lines = block.split('\n').filter(Boolean)
  let event = 'message'
  let data = ''

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      data = line.slice(5).trim()
    }
  }

  if (!data) {
    return null
  }

  try {
    const parsed = JSON.parse(data) as Record<string, unknown>
    switch (event) {
      case 'session':
        return {
          event: 'session',
          data: parsed as { session_id: string; run_id: string },
        }
      case 'token':
        return { event: 'token', data: parsed as { text: string } }
      case 'tool_start':
        return {
          event: 'tool_start',
          data: parsed as { tool: string; input?: Record<string, unknown> },
        }
      case 'tool_end':
        return {
          event: 'tool_end',
          data: parsed as {
            tool: string
            input?: Record<string, unknown>
            duration_ms?: number
            success?: boolean
          },
        }
      case 'approval_required':
        return {
          event: 'approval_required',
          data: parsed as { approval_id: string; command: string; reason?: string },
        }
      case 'done':
        return {
          event: 'done',
          data: parsed as {
            session_id: string
            run_id: string
            pending_approval?: { approval_id: string; command: string; reason?: string } | null
          },
        }
      case 'error':
        return { event: 'error', data: parsed as { message: string } }
      default:
        return null
    }
  } catch {
    return null
  }
}

export async function consumeAgentSseStream(
  response: Response,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('响应不支持流式读取')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel()
        return
      }

      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() ?? ''

      for (const block of blocks) {
        const event = parseAgentSseBlock(block.trim())
        if (event) {
          onEvent(event)
        }
      }
    }

    if (buffer.trim()) {
      const event = parseAgentSseBlock(buffer.trim())
      if (event) {
        onEvent(event)
      }
    }
  } finally {
    reader.releaseLock()
  }
}
