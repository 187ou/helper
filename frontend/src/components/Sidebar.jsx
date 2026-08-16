import { useNavigate, useLocation } from 'react-router-dom'
import { cn } from '../utils'

const NAVS = [
  { key: 'dashboard', icon: '📋', label: '工作台看板', path: '/dashboard' },
  { key: 'tasks', icon: '✅', label: '任务管理', path: '/tasks' },
  { key: 'work', icon: '💼', label: '职场办公', path: '/work' },
  { key: 'life', icon: '🏠', label: '生活健康', path: '/life' },
  { key: 'text-tools', icon: '✏️', label: '文本处理', path: '/text-tools' },
  { key: 'chat', icon: '💬', label: 'AI 对话', path: '/chat' },
  { key: 'evolution', icon: '🧬', label: '进化中心', path: '/evolution' },
  { key: 'templates', icon: '📐', label: '模板库', path: '/templates' },
  { key: 'toolbox', icon: '🧰', label: '工具库', path: '/toolbox' },
  { key: 'memory', icon: '🧠', label: '记忆洞察', path: '/memory' },
  { key: 'reminders', icon: '🔔', label: '智能提醒', path: '/reminders' },
  { key: 'kb', icon: '📚', label: '知识库', path: '/kb' },
  { key: 'schedule-settings', icon: '⏰', label: '定时配置', path: '/schedule-settings' },
  { key: 'settings', icon: '⚙️', label: '系统设置', path: '/settings' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  // 根据当前路径确定激活项
  const current = NAVS.find((n) => location.pathname.startsWith(n.path))?.key || 'dashboard'

  return (
    <aside className="w-[200px] shrink-0 glass border-r border-white/30 flex flex-col py-5">
      {/* Logo */}
      <div className="px-6 pb-6 text-[15px] font-semibold text-[var(--color-accent)]">
        桌面助手
      </div>

      {/* 导航 */}
      <nav className="flex-1 px-3 space-y-1">
        {NAVS.map((item) => (
          <button
            key={item.key}
            onClick={() => navigate(item.path)}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-[13px] text-left transition-all',
              current === item.key
                ? 'glass-strong text-[var(--color-accent)] font-medium shadow-sm'
                : 'text-[var(--color-text-sec)] hover:bg-white/50 hover:text-[var(--color-text)]'
            )}
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* 版本 */}
      <div className="px-6 pt-4 text-[11px] text-[var(--color-text-muted)]">
        v1.0.0 · 本地私有
      </div>
    </aside>
  )
}
