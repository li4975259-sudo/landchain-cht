import { NavLink } from 'react-router-dom'
import { Bot, FileText, MessageSquare, Settings } from 'lucide-react'

const navItems = [
  { to: '/', label: '聊天', icon: MessageSquare, end: true },
  { to: '/agent', label: '智能体', icon: Bot },
  { to: '/documents', label: '文档', icon: FileText },
  { to: '/settings', label: '设置', icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="flex w-full shrink-0 flex-row border-r border-border bg-surface-raised md:w-56 md:flex-col">
      <div className="border-b border-border px-4 py-4 md:py-5">
        <h1 className="text-base font-semibold tracking-tight md:text-lg">LandChain</h1>
        <p className="mt-0.5 hidden text-xs text-text-muted md:block">RAG 知识库控制台</p>
      </div>
      <nav className="flex flex-1 gap-1 p-2 md:flex-col md:p-3">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors md:flex-none md:justify-start md:gap-3 md:py-2.5 ${
                isActive
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-muted hover:bg-surface-overlay hover:text-text'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
