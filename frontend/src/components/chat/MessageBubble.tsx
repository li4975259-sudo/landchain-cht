import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { UiMessage } from '../../types/api'
import { Bot, User } from 'lucide-react'

interface MessageBubbleProps {
  message: UiMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
          isUser ? 'bg-accent/20 text-accent' : 'bg-surface-overlay text-text-muted'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-accent text-white'
            : message.error
              ? 'border border-danger/40 bg-danger/10 text-red-100'
              : 'border border-border bg-surface-raised text-text'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose-chat">
            {message.content ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            ) : message.streaming ? (
              <span className="text-text-muted">正在检索与生成…</span>
            ) : null}
            {message.streaming && message.content && (
              <span className="cursor-blink ml-0.5 inline-block h-4 w-0.5 bg-accent align-middle" />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
