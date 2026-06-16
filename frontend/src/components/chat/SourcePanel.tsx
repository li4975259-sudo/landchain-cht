import { ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { useState } from 'react'
import type { SourceCitation } from '../../types/api'

interface SourcePanelProps {
  sources: string[]
  citations?: SourceCitation[]
  chunksUsed: number
}

function citationKey(citation: SourceCitation, index: number): string {
  return `${citation.source}-${citation.chunk_index ?? index}-${citation.heading_path ?? ''}`
}

export function SourcePanel({ sources, citations, chunksUsed }: SourcePanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const hasCitations = citations && citations.length > 0

  if (sources.length === 0 && !hasCitations && chunksUsed === 0) {
    return null
  }

  return (
    <aside
      className={`flex shrink-0 flex-col border-l border-border bg-surface-raised transition-all ${
        collapsed ? 'w-10' : 'w-72'
      }`}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-3">
        {!collapsed && (
          <div className="flex items-center gap-2 text-sm font-medium">
            <FileText className="h-4 w-4 text-accent" />
            引用来源
          </div>
        )}
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="rounded p-1 text-text-muted hover:bg-surface-overlay hover:text-text"
          aria-label={collapsed ? '展开引用面板' : '折叠引用面板'}
        >
          {collapsed ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>
      {!collapsed && (
        <div className="flex-1 overflow-y-auto p-4">
          <p className="mb-3 text-xs text-text-muted">本次检索使用 {chunksUsed} 个 chunk</p>
          {hasCitations ? (
            <ul className="space-y-2">
              {citations.map((citation, index) => (
                <li
                  key={citationKey(citation, index)}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-muted"
                >
                  <p className="font-medium text-text">{citation.filename}</p>
                  {citation.heading_path && (
                    <p className="mt-1 pl-2 text-text-muted">└ {citation.heading_path}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : sources.length === 0 ? (
            <p className="text-sm text-text-muted">暂无引用来源</p>
          ) : (
            <ul className="space-y-2">
              {sources.map((source) => (
                <li
                  key={source}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-xs break-all text-text-muted"
                >
                  {source}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </aside>
  )
}
