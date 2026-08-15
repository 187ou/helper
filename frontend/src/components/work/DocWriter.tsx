import { useState } from 'react'
import {
  Card, Button, Input, Select, Space, Tabs, message, Spin, Tooltip,
} from 'antd'
import {
  FileTextOutlined, SaveOutlined, CopyOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

const { TextArea } = Input

export default function DocWriter() {
  const [activeType, setActiveType] = useState('weekly')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')
  const [title, setTitle] = useState('')

  // 周报
  const [workItems, setWorkItems] = useState('')
  const [notes, setNotes] = useState('')
  // 月报
  const [month, setMonth] = useState('')
  const [highlights, setHighlights] = useState('')
  // 会议纪要
  const [meetingText, setMeetingText] = useState('')
  // 润色
  const [polishText, setPolishText] = useState('')
  const [style, setStyle] = useState('正式')

  async function generate() {
    setLoading(true)
    setResult('')
    try {
      let res
      if (activeType === 'weekly') {
        const items = workItems.split('\n').filter(Boolean)
        res = await api.genWeekly({ work_items: items, notes })
      } else if (activeType === 'monthly') {
        const hl = highlights.split('\n').filter(Boolean)
        res = await api.genMonthly({ month, highlights: hl })
      } else if (activeType === 'meeting') {
        res = await api.genMeeting({ raw_text: meetingText })
      } else {
        res = await api.polishDoc({ text: polishText, style })
      }
      setResult(res.content)
      message.success('生成完成')
    } catch (e: any) {
      message.error(e.message || '生成失败')
    } finally {
      setLoading(false)
    }
  }

  async function save() {
    if (!result) return
    const docTitle = title || (activeType === 'weekly' ? '周报' : activeType === 'monthly' ? '月报' : '文书')
    await api.saveDoc({ title: docTitle, content: result })
    message.success('已保存到本地')
  }

  function copy() {
    navigator.clipboard.writeText(result)
    message.success('已复制')
  }

  const tabItems = [
    {
      key: 'weekly',
      label: '周报',
      children: (
        <Space direction="vertical" className="w-full" size="middle">
          <div>
            <label className="text-xs text-gray-500 block mb-1">本周工作成果（每行一项）</label>
            <TextArea rows={4} value={workItems} onChange={(e) => setWorkItems(e.target.value)}
              placeholder="完成用户模块开发&#10;修复 3 个线上 bug&#10;编写技术文档 5 篇" />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">备注</label>
            <TextArea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="其他补充..." />
          </div>
        </Space>
      ),
    },
    {
      key: 'monthly',
      label: '月报',
      children: (
        <Space direction="vertical" className="w-full" size="middle">
          <div>
            <label className="text-xs text-gray-500 block mb-1">月份</label>
            <Input value={month} onChange={(e) => setMonth(e.target.value)} placeholder="2026年8月" />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">本月亮点（每行一项）</label>
            <TextArea rows={4} value={highlights} onChange={(e) => setHighlights(e.target.value)}
              placeholder="项目顺利上线&#10;性能优化提升 30%" />
          </div>
        </Space>
      ),
    },
    {
      key: 'meeting',
      label: '会议纪要',
      children: (
        <div>
          <label className="text-xs text-gray-500 block mb-1">会议记录/草稿</label>
          <TextArea rows={6} value={meetingText} onChange={(e) => setMeetingText(e.target.value)}
            placeholder="粘贴会议内容、语音转文字结果..." />
        </div>
      ),
    },
    {
      key: 'polish',
      label: '公文润色',
      children: (
        <Space direction="vertical" className="w-full" size="middle">
          <Select value={style} onChange={setStyle} style={{ width: 160 }}>
            <Select.Option value="正式">正式严谨</Select.Option>
            <Select.Option value="简洁">简洁明了</Select.Option>
            <Select.Option value="活泼">活泼亲和</Select.Option>
          </Select>
          <div>
            <label className="text-xs text-gray-500 block mb-1">原文</label>
            <TextArea rows={5} value={polishText} onChange={(e) => setPolishText(e.target.value)} placeholder="输入需要润色的文本..." />
          </div>
        </Space>
      ),
    },
  ]

  return (
    <div className="flex gap-4 h-full">
      {/* 左侧输入 */}
      <div className="w-1/2 flex flex-col gap-3">
        <Tabs activeKey={activeType} onChange={setActiveType} items={tabItems} size="small" />
        <div className="flex gap-2">
          <Button type="primary" icon={<ReloadOutlined />} onClick={generate} loading={setLoading}>
            生成
          </Button>
        </div>
      </div>

      {/* 右侧结果 */}
      <div className="w-1/2 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="文档标题（可选）" className="flex-1 mr-2" />
          <Space>
            <Tooltip title="复制内容">
              <Button icon={<CopyOutlined />} onClick={copy} disabled={!result} />
            </Tooltip>
            <Tooltip title="保存到本地">
              <Button icon={<SaveOutlined />} onClick={save} disabled={!result} />
            </Tooltip>
          </Space>
        </div>
        <Card size="small" className="flex-1 overflow-y-auto">
          <Spin spinning={loading}>
            {result ? (
              <pre className="whitespace-pre-wrap text-sm font-sans">{result}</pre>
            ) : (
              <div className="text-gray-400 text-sm text-center py-12">
                <FileTextOutlined className="text-3xl mb-2 block" />
                点击「生成」按钮创建文书
              </div>
            )}
          </Spin>
        </Card>
      </div>
    </div>
  )
}
