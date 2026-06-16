import { useState } from 'react'
import { ingestDocuments, uploadDocument } from '../api/documents'
import { IngestButton } from '../components/documents/IngestButton'
import { UploadDropzone } from '../components/documents/UploadDropzone'
import { UploadHistory } from '../components/documents/UploadHistory'
import { ErrorBanner } from '../components/common/ErrorBanner'
import type { UploadRecord } from '../types/api'

export function DocumentsPage() {
  const [records, setRecords] = useState<UploadRecord[]>([])
  const [uploading, setUploading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ingestResult, setIngestResult] = useState<string | null>(null)

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError(null)
    setIngestResult(null)
    try {
      const result = await uploadDocument(file)
      setRecords((prev) => [
        {
          id: crypto.randomUUID(),
          filename: result.filename,
          chunksAdded: result.chunks_added,
          sources: result.sources,
          uploadedAt: new Date().toISOString(),
        },
        ...prev,
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
      throw err
    } finally {
      setUploading(false)
    }
  }

  const handleIngest = async () => {
    setIngesting(true)
    setError(null)
    setIngestResult(null)
    try {
      const result = await ingestDocuments()
      const skipped =
        result.skipped.length > 0 ? `，跳过 ${result.skipped.length} 个文件` : ''
      setIngestResult(
        `扫描完成：处理 ${result.files_processed} 个文件，新增 ${result.chunks_added} chunks${skipped}`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : '扫描失败')
    } finally {
      setIngesting(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-8">
        <section>
          <h3 className="mb-2 text-base font-semibold">上传文档</h3>
          <p className="mb-4 text-sm text-text-muted">
            上传后将立即写入向量库，可用于 RAG 问答检索。
          </p>
          <UploadDropzone onUpload={handleUpload} disabled={uploading} />
          {uploading && (
            <p className="mt-3 text-sm text-text-muted">正在上传并入库…</p>
          )}
        </section>

        <section className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold">批量导入</h3>
            <p className="mt-1 text-sm text-text-muted">
              扫描后端 `data/` 目录，增量导入已有文档。
            </p>
          </div>
          <IngestButton onIngest={handleIngest} loading={ingesting} />
        </section>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {ingestResult && (
          <div className="rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-green-200">
            {ingestResult}
          </div>
        )}

        <section>
          <h3 className="mb-4 text-base font-semibold">上传记录</h3>
          <UploadHistory records={records} />
        </section>
      </div>
    </div>
  )
}
