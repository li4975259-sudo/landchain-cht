import { Link } from 'react-router-dom'
import { Bot, Plus, Trash2 } from 'lucide-react'
import { ChatInput } from '../components/chat/ChatInput'
import { MessageList } from '../components/chat/MessageList'
import { SourcePanel } from '../components/chat/SourcePanel'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { useChat } from '../hooks/useChat'

const AGENT_INTENT = /postgres|集合|explore_data|run_task|list_tasks|考勤|统计.*(今日|昨天|uv|pv)|生成.*报告|query_data/i

export function ChatPage() {
  const {
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
  } = useChat()

  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const showAgentHint =
    (lastUser && AGENT_INTENT.test(lastUser.content)) ||
    (lastAssistant?.content.includes('知识库中未找到相关内容') &&
      lastUser &&
      AGENT_INTENT.test(lastUser.content))

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-border px-6 py-3">
          <span className="text-sm text-text-muted">知识库 RAG 聊天</span>
          <button
            type="button"
            onClick={newSession}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface-overlay"
          >
            <Plus className="h-3.5 w-3.5" />
            新建会话
          </button>
          <button
            type="button"
            onClick={() => void clearSession()}
            disabled={!sessionId && messages.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface-overlay disabled:opacity-40"
          >
            <Trash2 className="h-3.5 w-3.5" />
            清空记忆
          </button>
          {sessionId && (
            <span className="ml-auto truncate text-xs text-text-muted">
              会话 {sessionId.slice(0, 8)}…
            </span>
          )}
        </div>

        {error && <ErrorBanner message={error} />}

        {showAgentHint && (
          <div className="mx-6 mt-3 flex items-start gap-3 rounded-lg border border-accent/40 bg-accent/10 px-4 py-3 text-sm">
            <Bot className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
            <div>
              <p className="font-medium text-text">这类问题请使用「智能体」</p>
              <p className="mt-1 text-text-muted">
                查业务数据集合、跑统计脚本、生成报告需要工具调用，本页仅做文档 RAG 检索。
              </p>
              <Link
                to="/agent"
                className="mt-2 inline-block text-accent underline-offset-2 hover:underline"
              >
                前往超级智能体 →
              </Link>
            </div>
          </div>
        )}

        <MessageList messages={messages} isLoadingHistory={isLoadingHistory} />
        <ChatInput
          onSend={(text) => void sendMessage(text)}
          onStop={stopStreaming}
          disabled={isStreaming || isLoadingHistory}
          isStreaming={isStreaming}
        />
      </div>
      <div className="hidden lg:flex">
        <SourcePanel
          sources={lastSources}
          citations={lastCitations}
          chunksUsed={lastChunksUsed}
        />
      </div>
      {(lastCitations.length > 0 || lastSources.length > 0 || lastChunksUsed > 0) && (
        <div className="border-t border-border px-4 py-3 lg:hidden">
          <p className="mb-2 text-xs text-text-muted">引用来源（{lastChunksUsed} chunks）</p>
          <ul className="space-y-2">
            {lastCitations.length > 0
              ? lastCitations.map((citation, index) => (
                  <li key={`${citation.source}-${index}`} className="text-xs text-text-muted">
                    <p className="font-medium text-text">{citation.filename}</p>
                    {citation.heading_path && (
                      <p className="mt-0.5 pl-2">└ {citation.heading_path}</p>
                    )}
                  </li>
                ))
              : lastSources.map((source) => (
                  <li key={source} className="text-xs break-all text-text-muted">
                    {source}
                  </li>
                ))}
          </ul>
        </div>
      )}
    </div>
  )
}
