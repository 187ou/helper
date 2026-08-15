import { useState, useRef, useEffect } from 'react'
import { api } from '../api'

// 步骤状态: pending / running / done
const STATUS_ICON = { pending: '⏳', running: '▸', done: '✓' }
const STATUS_COLOR = {
  pending: 'text-[var(--color-text-muted)]',
  running: 'text-[var(--color-accent)] animate-pulse',
  done: 'text-[var(--color-success)]',
}

export default function Chat() {
  const [steps, setSteps] = useState([])
  const [logs, setLogs] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [configured, setConfigured] = useState(true)
  const logRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    api.checkConfigured().then((r) => setConfigured(r.configured))
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs, steps])

  async function send() {
    const text = input.trim()
    if (!text || loading) return

    if (!configured) {
      setLogs((l) => [...l, { type: 'error', text: '⚠️ 请先在「设置」配置 API Key' }])
      return
    }

    setSteps([])
    setLogs([{ type: 'user', text }])
    setInput('')
    setLoading(true)

    try {
      const controller = new AbortController()
      abortRef.current = controller

      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // 解析 SSE 事件
        while (true) {
          const eventEnd = buffer.indexOf('\n\n')
          if (eventEnd === -1) break

          const block = buffer.slice(0, eventEnd)
          buffer = buffer.slice(eventEnd + 2)

          const lines = block.split('\n')
          let eventType = ''
          let dataStr = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7)
            else if (line.startsWith('data: ')) dataStr = line.slice(6)
          }

          if (eventType && dataStr) {
            try {
              const data = JSON.parse(dataStr)
              handleEvent(eventType, data)
            } catch {}
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setLogs((l) => [...l, { type: 'error', text: `连接失败: ${e.message}` }])
      }
    }

    setLoading(false)
  }

  function handleEvent(type, data) {
    switch (type) {
      case 'steps':
        setSteps(data.steps.map((s) => ({ ...s, status: 'pending', output: '' })))
        break

      case 'step_start':
        setSteps((prev) =>
          prev.map((s) => (s.index === data.index ? { ...s, status: 'running', output: '' } : s))
        )
        break

      case 'token':
        // 逐字追加到对应步骤
        setSteps((prev) =>
          prev.map((s) =>
            s.index === data.index ? { ...s, output: (s.output || '') + data.text } : s
          )
        )
        break

      case 'step_done':
        setSteps((prev) =>
          prev.map((s) => (s.index === data.index ? { ...s, status: 'done' } : s))
        )
        break

      case 'log':
        setLogs((l) => [...l, { type: 'log', text: data.message }])
        break

      case 'done':
        setSteps((prev) => prev.map((s) => (s.status === 'running' ? { ...s, status: 'done' } : s)))
        setLogs((l) => [
          ...l,
          { type: 'success', text: `✓ 完成 · ${(data.cost_time || 0).toFixed(1)}s` },
        ])
        break

      case 'error':
        setLogs((l) => [...l, { type: 'error', text: data.message }])
        break
    }
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

      {/* 拆解步骤 + 流式输出 */}
      {steps.length > 0 && (
        <div className="flex-1 glass rounded-2xl p-4 overflow-y-auto min-h-0">
          <div className="text-xs text-[var(--color-text-sec)] mb-3">
            📋 任务拆解 ({steps.length} 步)
          </div>
          <div className="space-y-3">
            {steps.map((step) => (
              <div
                key={step.index}
                className={`p-3 rounded-xl transition-all ${
                  step.status === 'running'
                    ? 'bg-[var(--color-accent-soft)] border border-[var(--color-accent)]'
                    : step.status === 'done'
                      ? 'bg-green-50/50'
                      : 'bg-white/40'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={STATUS_COLOR[step.status]}>{STATUS_ICON[step.status]}</span>
                  <span className="font-medium text-sm text-[var(--color-text)]">{step.name}</span>
                  <span className="text-xs text-[var(--color-text-muted)] ml-auto">
                    {step.type === 'parallel' ? '并行' : '串行'}
                  </span>
                </div>
                {step.desc && (
                  <p className="text-xs text-[var(--color-text-sec)] mt-1 ml-6">{step.desc}</p>
                )}
                {/* 流式输出内容 */}
                {(step.output || step.status === 'running') && (
                  <div className="mt-2 ml-6 text-sm text-[var(--color-text-sec)] leading-relaxed whitespace-pre-wrap">
                    {step.output}
                    {step.status === 'running' && (
                      <span className="inline-block w-1.5 h-4 bg-[var(--color-accent)] ml-0.5 animate-pulse align-middle" />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 日志区 */}
      {steps.length === 0 && (
        <div ref={logRef} className="flex-1 glass rounded-2xl p-4 overflow-y-auto min-h-0">
          <div className="space-y-1 text-sm leading-relaxed">
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
                }[log.type] || ''}
              >
                {log.type === 'log' ? `› ${log.text}` : log.text}
              </div>
            ))}
          </div>
        </div>
      )}

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
