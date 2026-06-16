import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../api/health'
import type { HealthResponse } from '../types/api'

const DEFAULT_INTERVAL = 30_000

export function useHealth(intervalMs = DEFAULT_INTERVAL) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getHealth()
      setHealth(data)
    } catch (err) {
      setHealth(null)
      setError(err instanceof Error ? err.message : '无法连接后端服务')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    if (intervalMs <= 0) {
      return
    }
    const timer = window.setInterval(() => {
      void refresh()
    }, intervalMs)
    return () => window.clearInterval(timer)
  }, [refresh, intervalMs])

  return { health, loading, error, refresh }
}
