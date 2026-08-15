import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Input, Tag, Spin, Tooltip, message, Space, Card, Avatar, Modal, Collapse,
} from 'antd'
import {
  SendOutlined, StopOutlined, RobotOutlined, UserOutlined,
  DeleteOutlined, HistoryOutlined, ClearOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import { api } from '../api'
import FeedbackCollector from '../components/FeedbackCollector'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  steps?: ChatStep[]
  timestamp: number
}

interface ChatStep {
  index: number
  name: string
  desc: string
  type: string
  status: 'pending' | 'running' | 'done'
  output: string
}

const STORAGE_KEY = 'chat_history'

export default function Chat() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [configured, setConfigured] = useState(true)
  const [currentSteps, setCurrentSteps] = useState<ChatStep[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [createdTaskIds, setCreatedTaskIds] = useState<number[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // 加载历史记录
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        setMessages(JSON.parse(saved))
      }
    } catch {}
    api.checkConfigured().then((r) => setConfigured(r.configured))
  }, [])

  // 保存历史记录
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentSteps])

  const generateId = () => Date.now().toString(36) + Math.random().toString(36).slice(2)

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return

    if (!configured) {
      setMessages((prev) => [...prev, {
        id: generateId(), role: 'assistant', content: '⚠️ 请先在「设置」配置 API Key', timestamp: Date.now(),
      }])
      return
    }

    const userMessage: ChatMessage = { id: generateId(), role: 'user', content: text, timestamp: Date.now() }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setCurrentSteps([])

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
      const stepsData: ChatStep[] = []
      let lastStepOutput = ''  // 最后一步的输出作为最终回复

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
              handleStreamEvent(eventType, data, stepsData)

              // 记录最后一步的输出作为最终回复
              if (eventType === 'token' && stepsData.length > 0) {
                const currentStep = stepsData[data.index]
                if (currentStep && data.index === stepsData.length - 1) {
                  lastStepOutput += data.text
                }
              }
            } catch {}
          }
        }
      }

      // 完成时添加 AI 消息（只包含最终回复，不包含执行过程）
      const finalContent = lastStepOutput.trim() || '任务已执行完成'
      const aiMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: finalContent,
        steps: stepsData.length > 0 ? stepsData : undefined,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, aiMessage])

      // 提示查看创建的任务
      if (createdTaskIds.length > 0) {
        setTimeout(() => {
          message.success(
            <span>已创建 {createdTaskIds.length} 个任务 <Button type="link" size="small" onClick={() => navigate('/tasks')}>查看任务</Button></span>
          )
        }, 500)
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setMessages((prev) => [...prev, {
          id: generateId(), role: 'assistant', content: `❌ 连接失败: ${e.message}`, timestamp: Date.now(),
        }])
      }
    }

    setLoading(false)
    setCurrentSteps([])
  }, [input, loading, configured])

  function handleStreamEvent(type: string, data: any, stepsData: ChatStep[]) {
    switch (type) {
      case 'steps':
        stepsData.length = 0
        data.steps.forEach((s: any) => {
          stepsData.push({ ...s, status: 'pending', output: '' })
        })
        setCurrentSteps([...stepsData])
        break
      case 'step_start':
        updateStep(stepsData, data.index, { status: 'running', output: '' })
        break
      case 'token':
        updateStep(stepsData, data.index, { output: (stepsData[data.index]?.output || '') + data.text })
        break
      case 'step_done':
        updateStep(stepsData, data.index, { status: 'done' })
        break
      case 'done':
        stepsData.forEach((_, i) => updateStep(stepsData, i, { status: 'done' }))
        break
    }
  }

  function updateStep(stepsData: ChatStep[], index: number, update: Partial<ChatStep>) {
    if (stepsData[index]) {
      Object.assign(stepsData[index], update)
      setCurrentSteps([...stepsData])
    }
  }

  function stop() {
    abortRef.current?.abort()
    setLoading(false)
  }

  function clearHistory() {
    Modal.confirm({
      title: '清空对话历史',
      content: '确定要清空所有对话记录吗？',
      okText: '清空',
      okType: 'danger',
      onOk: () => {
        setMessages([])
        localStorage.removeItem(STORAGE_KEY)
        message.success('已清空')
      },
    })
  }

  function deleteMessage(id: string) {
    setMessages((prev) => prev.filter((m) => m.id !== id))
  }

  const statusIcon = { pending: '⏳', running: '▸', done: '✓' }
  const statusColor = { pending: 'text-gray-400', running: 'text-indigo-500', done: 'text-green-500' }

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100">
        <div>
          <h1 className="text-lg font-semibold text-[var(--color-text)]">AI 对话</h1>
          <p className="text-xs text-[var(--color-text-muted)]">
            输入指令，AI 自动拆解执行 · 对话自动保存
          </p>
        </div>
        <Space>
          <Button icon={<HistoryOutlined />} size="small" onClick={() => setShowHistory(true)}>
            历史 ({messages.length})
          </Button>
          <Button icon={<ClearOutlined />} size="small" danger onClick={clearHistory}>
            清空
          </Button>
        </Space>
      </div>

      {/* 对话区域 */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="text-center py-16">
            <RobotOutlined className="text-5xl text-gray-300 mb-4 block" />
            <p className="text-gray-400">输入指令，AI 将自动拆解并执行任务</p>
            <p className="text-xs text-gray-300 mt-2">对话记录自动保存在本地</p>
          </div>
        )}

        {/* 消息列表 */}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            {/* 头像 */}
            <Avatar
              size={36}
              icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              className={msg.role === 'user' ? 'bg-indigo-500 shrink-0' : 'bg-green-500 shrink-0'}
            />

            {/* 消息内容 */}
            <div className={`max-w-[70%] group ${msg.role === 'user' ? 'text-right' : ''}`}>
              <div
                className={`inline-block px-4 py-3 rounded-2xl text-sm leading-relaxed text-left ${
                  msg.role === 'user'
                    ? 'bg-indigo-500 text-white rounded-tr-sm'
                    : 'bg-gray-100 text-gray-800 rounded-tl-sm'
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* 任务步骤展示 - 可折叠，默认收起 */}
                {msg.steps && msg.steps.length > 0 && (
                  <div className="mt-2">
                    <Collapse
                      size="small"
                      defaultActiveKey={[]}
                      items={[{
                        key: 'steps',
                        label: (
                          <span className="text-xs text-gray-500">
                            📋 执行过程 ({msg.steps.length} 步)
                            <span className="ml-2 text-gray-400">点击展开</span>
                          </span>
                        ),
                        children: (
                          <div className="space-y-1.5 pt-1">
                            {msg.steps.map((step) => (
                              <div key={step.index} className="flex items-center gap-2 text-xs">
                                <span className={statusColor[step.status]}>{statusIcon[step.status]}</span>
                                <span className="font-medium text-gray-700">{step.name}</span>
                                <Tag className="text-[10px] ml-auto">{step.type === 'parallel' ? '并行' : '串行'}</Tag>
                              </div>
                            ))}
                          </div>
                        ),
                      }]}
                    />
                  </div>
                )}
              </div>

              {/* 时间和操作 */}
              <div className={`flex items-center gap-2 mt-1 text-[10px] text-gray-400 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {new Date(msg.timestamp).toLocaleTimeString()}
                {msg.role === 'assistant' && (
                  <FeedbackCollector
                    context={{ original: msg.content }}
                    size="small"
                  />
                )}
                <button
                  className="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"
                  onClick={() => deleteMessage(msg.id)}
                >
                  <DeleteOutlined />
                </button>
              </div>
            </div>
          </div>
        ))}

        {/* 当前正在进行的步骤 */}
        {loading && currentSteps.length > 0 && (
          <div className="flex gap-3">
            <Avatar size={36} icon={<RobotOutlined />} className="bg-green-500 shrink-0" />
            <div className="max-w-[70%]">
              <div className="inline-block px-4 py-3 rounded-2xl rounded-tl-sm bg-gray-100">
                <div className="space-y-2">
                  {currentSteps.map((step) => (
                    <div key={step.index} className="flex items-center gap-2 text-xs">
                      <span className={statusColor[step.status]}>{statusIcon[step.status]}</span>
                      <span className="font-medium">{step.name}</span>
                      {step.status === 'running' && <Spin size="small" className="ml-1" />}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 加载指示 */}
        {loading && currentSteps.length === 0 && (
          <div className="flex gap-3">
            <Avatar size={36} icon={<RobotOutlined />} className="bg-green-500 shrink-0" />
            <div className="inline-block px-4 py-3 rounded-2xl rounded-tl-sm bg-gray-100">
              <Spin size="small" /> <span className="text-sm text-gray-500 ml-2">思考中...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 底部操作栏 */}
      {createdTaskIds.length > 0 && (
        <div className="px-6 py-2 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
          <span className="text-xs text-gray-500">
            ✅ AI 已创建 {createdTaskIds.length} 个任务
          </span>
          <Space>
            <Button size="small" icon={<UnorderedListOutlined />} onClick={() => navigate('/tasks')}>
              查看任务
            </Button>
          </Space>
        </div>
      )}

      {/* 输入区 */}
      <div className="px-6 py-4 border-t border-gray-100 bg-white">
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
            autoSize={{ minRows: 1, maxRows: 4 }}
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
      </div>

      {/* 历史记录弹窗 */}
      <Modal
        title="对话历史"
        open={showHistory}
        onCancel={() => setShowHistory(false)}
        footer={null}
        width={600}
      >
        <div className="max-h-96 overflow-y-auto space-y-2">
          {messages.length === 0 && <p className="text-gray-400 text-center py-8">暂无对话记录</p>}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`p-3 rounded-lg cursor-pointer hover:bg-gray-50 ${
                msg.role === 'user' ? 'bg-indigo-50' : 'bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Tag color={msg.role === 'user' ? 'blue' : 'green'} className="text-xs">
                  {msg.role === 'user' ? '我' : 'AI'}
                </Tag>
                <span className="text-[10px] text-gray-400">
                  {new Date(msg.timestamp).toLocaleString()}
                </span>
              </div>
              <div className="text-sm text-gray-700 truncate">{msg.content}</div>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  )
}
