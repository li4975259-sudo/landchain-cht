import { getApiBase } from './client'
import type { IngestResponse, UploadResponse } from '../types/api'

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${getApiBase()}/documents/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let message = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) {
        message = body.detail
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  return (await response.json()) as UploadResponse
}

export async function ingestDocuments(): Promise<IngestResponse> {
  const response = await fetch(`${getApiBase()}/documents/ingest`, {
    method: 'POST',
  })

  if (!response.ok) {
    let message = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) {
        message = body.detail
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  return (await response.json()) as IngestResponse
}
