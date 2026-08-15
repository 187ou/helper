import { useState, useEffect } from 'react'
import { api } from '../api'

const TYPE_MAP = { flow: '优化', tool: '工具', template: '模板', weight: '权重' }
const FILTERS = ['全部', '流程优化', '工具新增', '模板固化', '权重迭代']
const FILTER_MAP = { '流程优化': 'flow', '工具新增': 'tool', '模板固化': 'template', '权重迭代': 'weight' }

export default function Evolution() {
  const [stats, setStats] = useState({})
  const [logs, setLogs] = useState([])
  const [weights, setWeights] = useState([])
  const [filter, setFilter] = useState('全部')

  useEffect(() => {
    api.getStats().then(setStats)
    api.getWeights().then(setWeights)
  }, [])

  useEffect(() => {
    const type = FILTER_MAP[filter] || ''
    api.getLogs(type).then(setLogs)
  }, [filter])

  return (
    <div className="h-full flex flex-col p-8 gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">进化中心</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">系统自我优化记录 · 记忆权重分布</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: '流程优化', value: stats.flow_optimizations || 0 },
          { label: '工具', value: stats.tool_count || 0 },
          { label: '模板', value: stats.template_count || 0 },
        ].map((s) => (
          <div key={s.label} className="glass rounded-2xl p-4 text-center">
            <div className="text-2xl font-semibold text-[var(--color-text)]">{s.value}</div>
            <div className="text-[11px] text-[var(--color-text-muted)] mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* 筛选 */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-[var(--color-text-sec)]">筛选:</span>
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
              filter === f
                ? 'bg-[var(--color-accent)] text-white'
                : 'bg-white/50 text-[var(--color-text-sec)] hover:bg-white/70'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
        {/* 时间轴 */}
        <div className="glass rounded-2xl p-5 overflow-hidden flex flex-col">
          <span className="text-xs font-medium text-[var(--color-text-sec)] mb-3">📜 时间轴</span>
          <div className="flex-1 overflow-y-auto space-y-1">
            {logs.length === 0 && <p className="text-xs text-[var(--color-text-muted)]">暂无</p>}
            {logs.map((log, i) => (
              <div key={i} className="text-sm p-2 hover:bg-white/40 rounded-lg">
                <span className="text-[var(--color-text-muted)]">{log.evo_time?.slice(0, 10)}</span>
                <span className="ml-3">{TYPE_MAP[log.evo_type] || log.evo_type}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 权重 */}
        <div className="glass rounded-2xl p-5 overflow-hidden flex flex-col">
          <span className="text-xs font-medium text-[var(--color-text-sec)] mb-3">🧠 记忆权重</span>
          <div className="flex-1 overflow-y-auto space-y-2">
            {weights.length === 0 && <p className="text-xs text-[var(--color-text-muted)]">暂无</p>}
            {weights.map((h, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className="w-12 text-[var(--color-text-sec)]">{h.habit_key}</span>
                <div className="flex-1 h-2 bg-white/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[var(--color-accent)] rounded-full"
                    style={{ width: `${Math.min(h.weight * 10, 100)}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--color-text-muted)] w-8 text-right">{h.weight.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
