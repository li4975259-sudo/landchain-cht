import { useEffect, useRef } from 'react'
import type { UiMessage } from '../../types/api'
import { MessageBubble } from './MessageBubble'
import { Spinner } from '../common/Spinner'
import { MessageSquare } from 'lucide-react'

interface MessageListProps {
  messages: UiMessage[]
  isLoadingHistory: boolean
}

export function MessageList({ messages, isLoadingHistory }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (isLoadingHistory) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner label="加载会话历史…" />
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center text-text-muted">
        <MessageSquare className="h-12 w-12 opacity-40" />
        <div>
          <p className="text-base font-medium text-text">开始与知识库对话</p>
          <p className="mt-1 max-w-md text-sm">
            基于 LandChain RAG 检索增强生成，支持多轮上下文记忆与引用来源展示。
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
