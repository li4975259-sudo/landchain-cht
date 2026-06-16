import type { ReactNode } from 'react'
import { ErrorBanner } from '../common/ErrorBanner'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { useHealth } from '../../hooks/useHealth'

interface AppShellProps {
  title: string
  children: ReactNode
}

export function AppShell({ title, children }: AppShellProps) {
  const { health, loading, error } = useHealth()

  return (
    <div className="flex h-full flex-col md:flex-row">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        {!health?.ollama_reachable && !loading && (
          <ErrorBanner message="Ollama 服务不可用，请检查 Ollama 是否已启动并可访问。" />
        )}
        {error && loading === false && !health && (
          <ErrorBanner message={`无法连接后端：${error}`} />
        )}
        <Header title={title} health={health} healthLoading={loading} />
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
