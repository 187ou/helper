import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Dashboard() {
  const [items, setItems] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newCat, setNewCat] = useState('work')

  const load = () => api.getToday().then(setItems)
  useEffect(() => { load() }, [])

  const workItems = items.filter((i) => i.category === 'work')
  const lifeItems = items.filter((i) => i.category !== 'work')

  async function add() {
    if (!newTitle.trim()) return
    await api.addSchedule({ title: newTitle, category: newCat })
    setNewTitle('')
    setShowAdd(false)
    load()
  }

  async function complete(id) {
    await api.completeSchedule(id)
    load()
  }

  return (
    <div className="h-full flex flex-col p-8 gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">看板</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">今日工作清单 · 生活待办</p>
      </div>

      <div className="flex-1 grid grid-cols-2 gap-4">
        {/* 工作清单 */}
        <div className="glass rounded-2xl p-5 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-[var(--color-text-sec)]">💼 工作清单</span>
            <button
              onClick={() => { setNewCat('work'); setShowAdd(true) }}
              className="text-xs px-3 py-1 bg-[var(--color-accent)] text-white rounded-lg hover:bg-[var(--color-accent-hi)]"
            >
              + 添加
            </button>
          </div>
          <div className="flex-1 overflow-y-auto space-y-2">
            {workItems.length === 0 && <p className="text-xs text-[var(--color-text-muted)]">暂无</p>}
            {workItems.map((item) => (
              <div key={item.id} className="flex items-center justify-between p-3 bg-white/50 rounded-xl text-sm">
                <span>{item.title}</span>
                <button
                  onClick={() => complete(item.id)}
                  className="text-xs text-[var(--color-success)] hover:underline"
                >
                  完成
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* 生活待办 */}
        <div className="glass rounded-2xl p-5 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-[var(--color-text-sec)]">🏠 生活待办</span>
            <button
              onClick={() => { setNewCat('life'); setShowAdd(true) }}
              className="text-xs px-3 py-1 bg-[var(--color-accent)] text-white rounded-lg hover:bg-[var(--color-accent-hi)]"
            >
              + 添加
            </button>
          </div>
          <div className="flex-1 overflow-y-auto space-y-2">
            {lifeItems.length === 0 && <p className="text-xs text-[var(--color-text-muted)]">暂无</p>}
            {lifeItems.map((item) => (
              <div key={item.id} className="flex items-center justify-between p-3 bg-white/50 rounded-xl text-sm">
                <span>{item.title}</span>
                <button
                  onClick={() => complete(item.id)}
                  className="text-xs text-[var(--color-success)] hover:underline"
                >
                  完成
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 添加弹窗 */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="glass-strong rounded-2xl p-6 w-80 space-y-4">
            <h3 className="font-medium">添加{newCat === 'work' ? '工作' : '生活'}</h3>
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="内容..."
              className="w-full px-4 py-2.5 rounded-xl bg-white/70 border border-[var(--color-border-mid)] outline-none text-sm"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && add()}
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-[var(--color-text-sec)] hover:bg-white/50 rounded-xl">
                取消
              </button>
              <button onClick={add} className="px-4 py-2 text-sm bg-[var(--color-accent)] text-white rounded-xl hover:bg-[var(--color-accent-hi)]">
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
