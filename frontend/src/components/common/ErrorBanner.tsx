import { AlertCircle, X } from 'lucide-react'

interface ErrorBannerProps {
  message: string
  onDismiss?: () => void
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="flex items-center gap-3 border-b border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-red-200">
      <AlertCircle className="h-4 w-4 shrink-0 text-danger" />
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="rounded p-1 hover:bg-danger/20"
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
