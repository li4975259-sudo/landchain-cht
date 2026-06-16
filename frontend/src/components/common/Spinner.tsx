import { Loader2 } from 'lucide-react'

interface SpinnerProps {
  className?: string
  label?: string
}

export function Spinner({ className = 'h-5 w-5', label }: SpinnerProps) {
  return (
    <span className="inline-flex items-center gap-2 text-text-muted">
      <Loader2 className={`animate-spin ${className}`} />
      {label && <span className="text-sm">{label}</span>}
    </span>
  )
}
