import { useState, useRef, useEffect } from 'react'
import {
  Button, Input, Tag, Spin, Tooltip, message, Segmented, Space, Card,
} from 'antd'
import {
  SendOutlined, StopOutlined, EyeOutlined, RobotOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

interface Step {
  index: number
  name: string
  desc: string
  type: string
  status: 'pending' | 'running' | 'done'
  output: string
}

interface Log {
  type: string
  text: string
}

export default function Chat() {
  const [steps, setSteps] = useState<Step[]>([])
  const [logs, setLogs] = useState<Log[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [configured, setConfigured] = useState(true)
  const [previewMode, setPreviewMode] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const navigate = useNavigate()

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
      setLogs((l) => [...l, { type: 'error', text: '请先在「设置」配置 API Key' }])
      return
    }

    setSteps([])
    setLogs([{ type: 'user', text }])
    setInput('')
    setLoading(true)
    setPreviewMode(false)

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

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

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
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setLogs((l) => [...l, { type: 'error', text: `连接失败: ${e.message}` }])
      }
    }

    setLoading(false)
  }

  function handleEvent(type: string, data: any) {
    switch (type) {
      case 'steps':
        setSteps(data.steps.map((s: any) => ({ ...s, status: 'pending', output: '' })))
        break
      case 'step_start':
        setSteps((prev) =>
          prev.map((s) => (s.index === data.index ? { ...s, status: 'running', output: '' } : s))
        )
        break
      case 'token':
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
        setLogs((l) => [...l, { type: 'success', text: `完成 · ${(data.cost_time || 0).toFixed(1)}s` }])
        break
      case 'error':
        setLogs((l) => [...l, { type: 'error', text: data.message }])
        break
    }
  }

  function stop() {
    abortRef.current?.abort()
    setLoading(false)
  }

  function viewDag() {
    // 跳转到 DAG 预览页（使用最后一个任务的 DAG）
    message.info('DAG 可视化可在任务详情页查看')
  }

  const statusIcon = { pending: '⏳', running: '▸', done: '✓' }
  const statusColor = {
    pending: 'text-gray-400',
    running: 'text-indigo-500 animate-pulse',
    done: 'text-green-500',
  }

  return (
    <div className="h-full flex flex-col p-6 gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">AI 对话</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            输入指令，AI 自动拆解执行 · 支持混合任务
          </p>
        </div>
        {steps.length > 0 && (
          <Button icon={<EyeOutlined />} onClick={viewDag}>
            查看 DAG
          </Button>
        )}
      </div>

      {/* 拆解步骤 + 流式输出 */}
      {steps.length > 0 ? (
        <Card className="flex-1 overflow-y-auto glass" title={`任务拆解 (${steps.length} 步)`}>
          <div className="space-y-3">
            {steps.map((step) => (
              <div
                key={step.index}
                className={`p-3 rounded-xl transition-all ${
                  step.status === 'running'
                    ? 'bg-indigo-50 border border-indigo-200'
                    : step.status === 'done'
                      ? 'bg-green-50/50'
                      : 'bg-white/40'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={statusColor[step.status]}>{statusIcon[step.status]}</span>
                  <span className="font-medium text-sm">{step.name}</span>
                  <Tag className="ml-auto text-xs">{step.type === 'parallel' ? '并行' : '串行'}</Tag>
                </div>
                {step.desc && <p className="text-xs text-gray-500 mt-1 ml-6">{step.desc}</p>}
                {(step.output || step.status === 'running') && (
                  <div className="mt-2 ml-6 text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                    {step.output}
                    {step.status === 'running' && (
                      <span className="inline-block w-1.5 h-4 bg-indigo-500 ml-0.5 animate-pulse align-middle" />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <div ref={logRef} className="flex-1 glass rounded-2xl p-4 overflow-y-auto">
          <div className="space-y-1 text-sm leading-relaxed">
            {logs.length === 0 && (
              <p className="text-gray-400 text-center mt-8">
                <RobotOutlined className="text-3xl block mx-auto mb-2" />
                输入指令，AI 将自动拆解并执行任务
              </p>
            )}
            {logs.map((log, i) => (
              <div
                key={i}
                className={{
                  user: 'font-medium text-gray-800',
                  log: 'text-gray-500 pl-2',
                  success: 'text-green-600 font-medium',
                  error: 'text-red-500',
                }[log.type] || ''}
              >
                {log.type === 'log' ? `› ${log.text}` : log.text}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 输入区 */}
      <Card className="glass-strong" size="small">
        <div className="flex gap-3 items-end">
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder="输入指令... (回车发送 / Shift+回车换行)"
            autoSize={{ minRows: 2, maxRows: 4 }}
            className="flex-1"
          />
          {loading ? (
            <Button danger icon={<StopOutlined />} onClick={stop}>停止</Button>
          ) : (
            <Button type="primary" icon={<SendOutlined />} onClick={send} disabled={!input.trim()}>
              发送
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}
