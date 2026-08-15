import { useState } from 'react'
import {
  Button, Input, InputNumber, Card, message, Spin, Empty,
} from 'antd'
import {
  RobotOutlined, SaveOutlined, CopyOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

const { TextArea } = Input

export default function DocSummarizer() {
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [maxLen, setMaxLen] = useState(500)
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState('')

  async function generate() {
    if (text.trim().length < 50) {
      message.warning('文档内容至少需要 50 字')
      return
    }
    setLoading(true)
    setSummary('')
    try {
      const res = await api.summarizeDoc({ text, title, max_length: maxLen })
      setSummary(res.summary)
    } catch (e: any) {
      message.error(e.message || '生成失败')
    } finally {
      setLoading(false)
    }
  }

  async function saveAsNote() {
    if (!summary) return
    await api.summarizeAndSave({ text, title, max_length: maxLen })
    message.success('已保存为笔记')
  }

  function copy() {
    navigator.clipboard.writeText(summary)
    message.success('已复制')
  }

  return (
    <div className="flex gap-4 h-full">
      {/* 输入区 */}
      <div className="w-1/2 flex flex-col gap-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">文档标题（可选）</label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：Q3 财报分析" />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">文档内容</label>
          <TextArea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="粘贴长文档内容（报告、合同、学习资料...）"
            className="font-mono text-sm"
            rows={14}
          />
          <div className="text-xs text-gray-400 mt-1">{text.length} 字</div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">摘要长度：</span>
          <InputNumber min={100} max={2000} step={100} value={maxLen} onChange={(v) => v && setMaxLen(v)} addonAfter="字" />
          <Button type="primary" icon={<RobotOutlined />} onClick={generate} loading={loading}>
            生成摘要
          </Button>
        </div>
      </div>

      {/* 结果区 */}
      <div className="w-1/2 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">🤖 智能摘要结果</span>
          <div className="flex gap-2">
            <Button size="small" icon={<CopyOutlined />} onClick={copy} disabled={!summary}>复制</Button>
            <Button size="small" type="primary" icon={<SaveOutlined />} onClick={saveAsNote} disabled={!summary}>
              保存为笔记
            </Button>
          </div>
        </div>
        <Card className="flex-1 overflow-y-auto">
          <Spin spinning={loading}>
            {summary ? (
              <pre className="whitespace-pre-wrap text-sm font-sans">{summary}</pre>
            ) : (
              <Empty description="粘贴文档内容后点击「生成摘要」" className="mt-16" />
            )}
          </Spin>
        </Card>
      </div>
    </div>
  )
}
