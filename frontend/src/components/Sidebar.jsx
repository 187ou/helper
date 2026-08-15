import { cn } from '../utils'

const NAVS = [
  { key: 'chat', icon: '💬', label: '对话' },
  { key: 'dashboard', icon: '📋', label: '看板' },
  { key: 'evolution', icon: '🧬', label: '进化' },
  { key: 'kb', icon: '📚', label: '知识库' },
  { key: 'settings', icon: '⚙️', label: '设置' },
]

export default function Sidebar({ current, onChange }) {
  return (
    <aside className="w-[180px] shrink-0 glass border-r border-white/30 flex flex-col py-5">
      {/* Logo */}
      <div className="px-6 pb-6 text-[15px] font-semibold text-[var(--color-accent)]">
        桌面助手
      </div>

      {/* 导航 */}
      <nav className="flex-1 px-3 space-y-1">
        {NAVS.map((item) => (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
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
        v1.0.0
      </div>
    </aside>
  )
}
