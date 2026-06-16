import { useState, type KeyboardEvent } from 'react'
import { Send, Square } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  onStop: () => void
  disabled: boolean
  isStreaming: boolean
  placeholder?: string
}

export function ChatInput({
  onSend,
  onStop,
  disabled,
  isStreaming,
  placeholder = '输入问题，Enter 发送，Shift+Enter 换行',
}: ChatInputProps) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    if (!value.trim() || disabled) {
      return
    }
    onSend(value)
    setValue('')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-border bg-surface-raised px-6 py-4">
      <div className="flex items-end gap-3">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled && !isStreaming}
          rows={3}
          className="min-h-[80px] flex-1 resize-none rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text outline-none placeholder:text-text-muted focus:border-accent disabled:opacity-60"
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-11 items-center gap-2 rounded-xl border border-border bg-surface-overlay px-4 text-sm hover:bg-surface"
          >
            <Square className="h-4 w-4" />
            停止
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            className="flex h-11 items-center gap-2 rounded-xl bg-accent px-4 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            发送
          </button>
        )}
      </div>
    </div>
  )
}
