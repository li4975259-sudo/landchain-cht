import { RefreshCw } from 'lucide-react'

interface IngestButtonProps {
  onIngest: () => Promise<void>
  loading: boolean
}

export function IngestButton({ onIngest, loading }: IngestButtonProps) {
  return (
    <button
      type="button"
      onClick={() => void onIngest()}
      disabled={loading}
      className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-4 py-2.5 text-sm hover:bg-surface-overlay disabled:opacity-60"
    >
      <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
      {loading ? '扫描中…' : '扫描 data/ 目录'}
    </button>
  )
}
