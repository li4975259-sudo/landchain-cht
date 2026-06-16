import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { AgentPage } from './pages/AgentPage'
import { ChatPage } from './pages/ChatPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { SettingsPage } from './pages/SettingsPage'

const titles: Record<string, string> = {
  '/': '知识库聊天',
  '/agent': '超级智能体',
  '/documents': '文档管理',
  '/settings': '系统设置',
}

function RoutedApp() {
  const location = useLocation()
  const title = titles[location.pathname] ?? 'LandChain'

  return (
    <AppShell title={title}>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/agent" element={<AgentPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <RoutedApp />
    </BrowserRouter>
  )
}
