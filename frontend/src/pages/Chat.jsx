import { useState, useRef, useEffect } from 'react'
import { api } from '../api'

export default function Chat() {
  const [logs, setLogs] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [configured, setConfigured] = useState(true)
  const logRef = useRef(null)

  useEffect(() => {
    api.checkConfigured().then((r) => setConfigured(r.configured))
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  async function send() {
    const text = input.trim()
    if (!text || loading) return

    if (!configured) {
      setLogs((l) => [...l, { type: 'error', text: '⚠️ 请先在「设置」配置 API Key' }])
      return
    }

    setLogs((l) => [...l, { type: 'user', text }])
    setInput('')
    setLoading(true)
    setLogs((l) => [...l, { type: 'info', text: '执行中...' }])

    try {
      const result = await api.sendMessage(text)
      setLogs((l) => {
        const next = l.slice(0, -1)
        return [...next, ...(result.logs || []).map((lg) => ({ type: 'log', text: lg })),
          { type: 'success', text: `✓ 完成 · ${(result.cost_time || 0).toFixed(1)}s` }]
      })
    } catch {
      setLogs((l) => [...l.slice(0, -1), { type: 'error', text: '执行失败' }])
    }
    setLoading(false)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="h-full flex flex-col p-8 gap-4">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">对话</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          输入指令，AI 自动执行 · 回车发送 / Shift+回车换行
        </p>
      </div>

      {/* 日志区 */}
      <div className="flex-1 glass rounded-2xl p-4 overflow-hidden">
        <div ref={logRef} className="h-full overflow-y-auto space-y-1 text-sm leading-relaxed">
          {logs.length === 0 && (
            <p className="text-[var(--color-text-muted)] text-center mt-8">执行日志...</p>
          )}
          {logs.map((log, i) => (
            <div
              key={i}
              className={{
                user: 'font-medium text-[var(--color-text)]',
                log: 'text-[var(--color-text-sec)] pl-2',
                success: 'text-[var(--color-success)] font-medium',
                error: 'text-[var(--color-danger)]',
                info: 'text-[var(--color-text-muted)] italic',
              }[log.type] || ''}
            >
              {log.type === 'log' ? `› ${log.text}` : log.text}
            </div>
          ))}
        </div>
      </div>

      {/* 输入区 */}
      <div className="glass-strong rounded-2xl p-3">
        <div className="flex gap-3 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入指令..."
            rows={2}
            className="flex-1 resize-none bg-transparent border-none outline-none text-sm p-2 placeholder:text-[var(--color-text-muted)]"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="px-5 py-2 bg-[var(--color-accent)] text-white rounded-xl text-sm font-medium hover:bg-[var(--color-accent-hi)] disabled:opacity-40 transition-all"
          >
            {loading ? '...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  )
}
