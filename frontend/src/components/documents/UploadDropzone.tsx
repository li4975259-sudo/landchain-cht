import { useCallback, useState, type DragEvent } from 'react'
import { Upload } from 'lucide-react'

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<void>
  disabled?: boolean
  maxSizeMb?: number
}

const ALLOWED = ['.pdf', '.txt', '.md']

export function UploadDropzone({
  onUpload,
  disabled = false,
  maxSizeMb = 20,
}: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false)

  const handleFile = useCallback(
    async (file: File) => {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
      if (!ALLOWED.includes(ext)) {
        throw new Error(`不支持的文件类型，仅支持 ${ALLOWED.join('、')}`)
      }
      if (file.size > maxSizeMb * 1024 * 1024) {
        throw new Error(`文件大小不能超过 ${maxSizeMb} MB`)
      }
      await onUpload(file)
    },
    [maxSizeMb, onUpload],
  )

  const onDrop = async (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) {
      return
    }
    const file = event.dataTransfer.files[0]
    if (file) {
      await handleFile(file)
    }
  }

  return (
    <label
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) {
          setDragging(true)
        }
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        void onDrop(event)
      }}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 transition-colors ${
        dragging
          ? 'border-accent bg-accent/10'
          : 'border-border bg-surface-raised hover:border-accent/50'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <Upload className="mb-3 h-10 w-10 text-text-muted" />
      <p className="text-sm font-medium">拖拽文件到此处，或点击选择</p>
      <p className="mt-1 text-xs text-text-muted">
        支持 PDF、TXT、Markdown，最大 {maxSizeMb} MB
      </p>
      <input
        type="file"
        className="hidden"
        accept=".pdf,.txt,.md"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) {
            void handleFile(file)
          }
          event.target.value = ''
        }}
      />
    </label>
  )
}
