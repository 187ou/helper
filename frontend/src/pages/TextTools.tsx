import { useState } from 'react'
import {
  Card, Button, Input, InputNumber, Select, Segmented, Space, message, Spin, Empty, Tooltip,
} from 'antd'
import {
  EditOutlined, CompressOutlined, ExpandOutlined, AlignLeftOutlined,
  CopyOutlined, RobotOutlined,
} from '@ant-design/icons'
import { api } from '../api'

const { TextArea } = Input

type ToolType = 'rewrite' | 'summarize' | 'expand' | 'format' | 'polish'

const TOOL_CONFIG: Record<ToolType, { label: string; icon: any; desc: string }> = {
  rewrite: { label: '改写', icon: <EditOutlined />, desc: '变换文风（正式/简洁/活泼）' },
  summarize: { label: '精简', icon: <CompressOutlined />, desc: '压缩为核心摘要' },
  expand: { label: '扩写', icon: <ExpandOutlined />, desc: '充实内容细节' },
  format: { label: '格式化', icon: <AlignLeftOutlined />, desc: '清理冗余、统一格式' },
  polish: { label: '润色', icon: <RobotOutlined />, desc: '综合优化处理' },
}

const STYLE_OPTIONS = [
  { value: '正式', label: '正式严谨' },
  { value: '简洁', label: '简洁明了' },
  { value: '活泼', label: '活泼亲和' },
  { value: '学术', label: '学术专业' },
  { value: '口语', label: '口语化' },
]

export default function TextTools() {
  const [tool, setTool] = useState<ToolType>('rewrite')
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  const [style, setStyle] = useState('正式')
  const [maxLen, setMaxLen] = useState(200)

  async function process() {
    if (!input.trim()) {
      message.warning('请输入文本')
      return
    }
    setLoading(true)
    setOutput('')
    try {
      let res
      const data = { text: input }
      switch (tool) {
        case 'rewrite':
          res = await api.rewriteText({ ...data, style })
          break
        case 'summarize':
          res = await api.summarizeText({ ...data, max_length: maxLen })
          break
        case 'expand':
          res = await api.expandText({ ...data, target_length: maxLen })
          break
        case 'format':
          res = await api.formatText(data)
          break
        case 'polish':
          res = await api.polishText({ ...data, goals: ['精简', '规范'] })
          break
      }
      setOutput(res.result)
    } catch (e: any) {
      message.error(e.message || '处理失败')
    } finally {
      setLoading(false)
    }
  }

  function copy() {
    navigator.clipboard.writeText(output)
    message.success('已复制')
  }

  function saveAsNote() {
    // 保存为知识库笔记
    api.createNote({ title: `文本处理: ${TOOL_CONFIG[tool].label}`, content: output, category: 'note' })
    message.success('已保存为笔记')
  }

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">文本智能处理</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          改写 · 精简 · 扩写 · 格式化 · 润色
        </p>
      </div>

      {/* 工具选择 */}
      <Card size="small" className="glass">
        <Segmented
          value={tool}
          onChange={(v) => setTool(v as ToolType)}
          options={Object.entries(TOOL_CONFIG).map(([key, cfg]) => ({
            label: (
              <div className="flex items-center gap-1.5 px-2">
                {cfg.icon}
                <span>{cfg.label}</span>
              </div>
            ),
            value: key,
          }))}
        />
        <div className="text-xs text-gray-400 mt-2">{TOOL_CONFIG[tool].desc}</div>
      </Card>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* 输入区 */}
        <div className="w-1/2 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">输入</span>
            <Space>
              {tool === 'rewrite' && (
                <Select value={style} onChange={setStyle} size="small" style={{ width: 100 }}>
                  {STYLE_OPTIONS.map((s) => (
                    <Select.Option key={s.value} value={s.value}>{s.label}</Select.Option>
                  ))}
                </Select>
              )}
              {(tool === 'summarize' || tool === 'expand') && (
                <InputNumber
                  size="small" min={50} max={2000} step={50}
                  value={maxLen} onChange={(v) => v && setMaxLen(v)}
                  addonAfter="字" style={{ width: 100 }}
                />
              )}
            </Space>
          </div>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入需要处理的文本..."
            className="flex-1 font-sono text-sm"
            style={{ minHeight: 300 }}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">{input.length} 字</span>
            <Button type="primary" icon={<RobotOutlined />} onClick={process} loading={loading}>
              处理
            </Button>
          </div>
        </div>

        {/* 输出区 */}
        <div className="w-1/2 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">输出</span>
            <Space>
              <Tooltip title="复制结果">
                <Button size="small" icon={<CopyOutlined />} onClick={copy} disabled={!output} />
              </Tooltip>
              <Tooltip title="保存为笔记">
                <Button size="small" onClick={saveAsNote} disabled={!output}>存为笔记</Button>
              </Tooltip>
            </Space>
          </div>
          <Card className="flex-1 overflow-y-auto">
            <Spin spinning={loading}>
              {output ? (
                <pre className="whitespace-pre-wrap text-sm font-sans">{output}</pre>
              ) : (
                <Empty description="处理结果将显示在这里" className="mt-16" />
              )}
            </Spin>
          </Card>
          <span className="text-xs text-gray-400">{output.length} 字</span>
        </div>
      </div>
    </div>
  )
}
