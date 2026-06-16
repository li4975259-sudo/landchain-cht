import { useEffect, useState } from 'react'
import { clearApiBaseOverride, getApiBase, setApiBase } from '../api/client'
import { useHealth } from '../hooks/useHealth'
import { Spinner } from '../components/common/Spinner'
import { StatusBadge } from '../components/common/StatusBadge'

export function SettingsPage() {
  const { health, loading, error, refresh } = useHealth(0)
  const [apiBase, setApiBaseInput] = useState(getApiBase())
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleSave = () => {
    setApiBase(apiBase)
    setSaved(true)
    window.setTimeout(() => setSaved(false), 2000)
  }

  const handleReset = () => {
    clearApiBaseOverride()
    setApiBaseInput(getApiBase())
    setSaved(true)
    window.setTimeout(() => setSaved(false), 2000)
    void refresh()
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto max-w-2xl space-y-8">
        <section className="rounded-xl border border-border bg-surface-raised p-6">
          <h3 className="text-base font-semibold">API 连接</h3>
          <p className="mt-1 text-sm text-text-muted">
            开发环境默认通过 Vite 代理访问 `/api`；生产环境可设置为后端地址。
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={apiBase}
              onChange={(event) => setApiBaseInput(event.target.value)}
              placeholder="/api 或 http://localhost:8000"
              className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleSave}
                className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
              >
                保存
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-surface-overlay"
              >
                恢复默认
              </button>
            </div>
          </div>
          {saved && <p className="mt-2 text-xs text-success">已保存</p>}
          <button
            type="button"
            onClick={() => void refresh()}
            className="mt-4 text-sm text-accent hover:underline"
          >
            检测连接
          </button>
        </section>

        <section className="rounded-xl border border-border bg-surface-raised p-6">
          <h3 className="text-base font-semibold">服务状态</h3>
          {loading && !health ? (
            <div className="mt-4">
              <Spinner label="检测中…" />
            </div>
          ) : error && !health ? (
            <p className="mt-4 text-sm text-danger">{error}</p>
          ) : health ? (
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-4">
                <dt className="text-text-muted">整体状态</dt>
                <dd>
                  <StatusBadge ok={health.status === 'ok'} label={health.status} />
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-text-muted">Ollama</dt>
                <dd>
                  <StatusBadge
                    ok={health.ollama_reachable}
                    label={health.ollama_reachable ? '可达' : '不可达'}
                  />
                </dd>
              </div>
              <InfoRow label="对话模型" value={health.chat_model} />
              <InfoRow label="嵌入模型" value={health.embed_model} />
              <InfoRow label="向量库 chunks" value={String(health.chunk_count)} />
              <InfoRow
                label="Qdrant"
                value={health.qdrant_reachable ? '可达' : '不可达'}
              />
              <InfoRow
                label="PostgreSQL"
                value={health.postgres_reachable ? '可达' : '不可达'}
              />
              <InfoRow
                label="Cross-Encoder 重排"
                value={health.rerank_enabled ? '已启用' : '已关闭'}
              />
              {health.rerank_enabled && (
                <InfoRow label="重排模型" value={health.rerank_model} />
              )}
            </dl>
          ) : null}
        </section>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-right break-all">{value}</dd>
    </div>
  )
}
