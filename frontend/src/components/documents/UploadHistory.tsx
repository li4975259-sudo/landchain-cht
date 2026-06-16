import type { UploadRecord } from '../../types/api'
import { FileText } from 'lucide-react'

interface UploadHistoryProps {
  records: UploadRecord[]
}

export function UploadHistory({ records }: UploadHistoryProps) {
  if (records.length === 0) {
    return (
      <p className="text-sm text-text-muted">暂无上传记录（仅当前会话内展示）</p>
    )
  }

  return (
    <ul className="space-y-3">
      {records.map((record) => (
        <li
          key={record.id}
          className="rounded-xl border border-border bg-surface-raised p-4"
        >
          <div className="flex items-start gap-3">
            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{record.filename}</p>
              <p className="mt-1 text-xs text-text-muted">
                {new Date(record.uploadedAt).toLocaleString()} · 新增 {record.chunksAdded}{' '}
                chunks
              </p>
              {record.sources.length > 0 && (
                <p className="mt-2 text-xs break-all text-text-muted">
                  来源：{record.sources.join('、')}
                </p>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}
