import { Bot, Plus, Trash2 } from 'lucide-react'
import { ChatInput } from '../components/chat/ChatInput'
import { MessageList } from '../components/chat/MessageList'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { useAgent } from '../hooks/useAgent'

export function AgentPage() {
  const {
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
  } = useAgent()

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-border px-6 py-3">
          <Bot className="h-4 w-4 text-accent" />
          <span className="text-sm font-medium">超级智能体</span>
          <button
            type="button"
            onClick={newSession}
            className="ml-2 inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface-overlay"
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

        {pendingApproval && (
          <div className="mx-6 mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
            <p className="font-medium text-amber-200">Shell 命令待审批</p>
            <p className="mt-1 break-all font-mono text-xs text-text-muted">
              {pendingApproval.command}
            </p>
            {pendingApproval.reason && (
              <p className="mt-1 text-xs text-text-muted">原因：{pendingApproval.reason}</p>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => void handleApprove()}
                className="rounded-lg bg-accent px-3 py-1.5 text-xs text-white"
              >
                批准执行
              </button>
              <button
                type="button"
                onClick={() => void handleReject()}
                className="rounded-lg border border-border px-3 py-1.5 text-xs"
              >
                拒绝
              </button>
            </div>
          </div>
        )}

        <MessageList messages={messages} isLoadingHistory={isLoadingHistory} />
        <ChatInput
          onSend={(text) => void sendMessage(text)}
          onStop={() => {}}
          disabled={isStreaming || isLoadingHistory}
          isStreaming={isStreaming}
          placeholder="例如：统计今日 UV 并生成文档；查 customer 集合标签分布…"
        />
      </div>
      <div className="hidden w-72 shrink-0 border-l border-border p-4 lg:block">
        <h3 className="mb-3 text-xs font-medium text-text-muted">工具调用</h3>
        {toolSteps.length === 0 ? (
          <p className="text-xs text-text-muted">Agent 执行工具时会在此展示步骤</p>
        ) : (
          <ul className="space-y-2">
            {toolSteps.map((step, idx) => (
              <li key={`${step.tool}-${idx}`} className="rounded-lg bg-surface-overlay p-2 text-xs">
                <span className="font-medium">{step.tool}</span>
                <span className="ml-2 text-text-muted">
                  {step.status === 'running' ? '运行中…' : '完成'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
