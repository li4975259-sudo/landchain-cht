const API_BASE_KEY = 'landchain_api_base'

export function getApiBase(): string {
  const stored = localStorage.getItem(API_BASE_KEY)
  if (stored) {
    return stored.replace(/\/$/, '')
  }
  const envBase = import.meta.env.VITE_API_BASE_URL as string | undefined
  return (envBase || '/api').replace(/\/$/, '')
}

export function setApiBase(url: string): void {
  localStorage.setItem(API_BASE_KEY, url.replace(/\/$/, ''))
}

export function clearApiBaseOverride(): void {
  localStorage.removeItem(API_BASE_KEY)
}

export class ApiClientError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg: string }[] }
    if (typeof body.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).join('; ')
    }
    return response.statusText
  } catch {
    return response.statusText || '请求失败'
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${getApiBase()}${path.startsWith('/') ? path : `/${path}`}`
  const response = await fetch(url, init)

  if (!response.ok) {
    const message = await parseError(response)
    throw new ApiClientError(message, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function apiFetchRaw(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const url = `${getApiBase()}${path.startsWith('/') ? path : `/${path}`}`
  const response = await fetch(url, init)

  if (!response.ok) {
    const message = await parseError(response)
    throw new ApiClientError(message, response.status)
  }

  return response
}
