import type { HealthResponse } from '../../types/api'
import { StatusBadge } from '../common/StatusBadge'
import { Spinner } from '../common/Spinner'

interface HeaderProps {
  title: string
  health: HealthResponse | null
  healthLoading: boolean
}

export function Header({ title, health, healthLoading }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-surface-raised px-6 py-4">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {health && (
          <p className="mt-0.5 text-xs text-text-muted">
            模型 {health.chat_model} · 向量库 {health.chunk_count} chunks
          </p>
        )}
      </div>
      <div className="flex items-center gap-3">
        {healthLoading && !health ? (
          <Spinner className="h-4 w-4" />
        ) : (
          <StatusBadge
            ok={health?.ollama_reachable ?? false}
            label={health?.ollama_reachable ? 'Ollama 在线' : 'Ollama 离线'}
          />
        )}
      </div>
    </header>
  )
}
