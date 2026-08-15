import { useState } from 'react'
import {
  Button, Input, Upload, message, Spin, Empty, Tag, Space, Table,
} from 'antd'
import {
  WalletOutlined, FileAddOutlined, CopyOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

const { TextArea } = Input

export default function Reimbursement() {
  const [texts, setTexts] = useState('')
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<any[]>([])
  const [report, setReport] = useState('')

  async function analyze() {
    if (!texts.trim()) {
      message.warning('请输入票据信息')
      return
    }
    setLoading(true)
    setItems([])
    try {
      const res = await api.analyzeReimbursement({ texts: texts.split('\n---\n') })
      setItems(res.items || [])
      if (res.total) message.success(`识别到 ${res.items?.length || 0} 项，合计 ¥${res.total.toFixed(2)}`)
      else message.info('未能识别票据信息，请补充后重试')
    } catch (e: any) {
      message.error(e.message || '分析失败')
    } finally {
      setLoading(false)
    }
  }

  async function genReport() {
    if (items.length === 0) return
    setLoading(true)
    try {
      const res = await api.genReimbursementReport({ items })
      setReport(res.content)
    } catch (e: any) {
      message.error(e.message || '生成失败')
    } finally {
      setLoading(false)
    }
  }

  const total = items.reduce((a, b) => a + (b.amount || 0), 0)

  const columns = [
    { title: '日期', dataIndex: 'date', width: 120, render: (d: string) => d || '—' },
    { title: '类别', dataIndex: 'category', width: 100, render: (c: string) => <Tag>{c || '其他'}</Tag> },
    { title: '金额', dataIndex: 'amount', width: 100, render: (a: number) => `¥${a?.toFixed(2)}` },
    { title: '摘要', dataIndex: 'summary', render: (s: string) => s || '—' },
  ]

  return (
    <div className="flex gap-4 h-full">
      <div className="w-2/5 flex flex-col gap-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">票据信息（每张票据用 --- 分隔）</label>
          <TextArea rows={8} value={texts} onChange={(e) => setTexts(e.target.value)}
            placeholder="2026-08-10 餐饮费 150元 客户招待&#10;---&#10;2026-08-12 打车费 45.5 出差往返" />
        </div>
        <Space>
          <Button type="primary" icon={<WalletOutlined />} onClick={analyze} loading={loading}>
            识别票据
          </Button>
          <Button icon={<FileAddOutlined />} onClick={genReport} disabled={items.length === 0} loading={loading}>
            生成报销单
          </Button>
        </Space>

        {items.length > 0 && (
          <div className="text-sm">
            合计：<Tag color="blue">¥{total.toFixed(2)}</Tag>（{items.length} 项）
          </div>
        )}
      </div>

      <div className="w-3/5 flex flex-col gap-3">
        <Spin spinning={loading}>
          {items.length === 0 && !report && (
            <Empty description="输入票据信息后点击识别" className="mt-16" />
          )}

          {items.length > 0 && !report && (
            <Table dataSource={items} columns={columns} rowKey={(_, i) => i} size="small" pagination={false} />
          )}

          {report && (
            <div className="space-y-2">
              <Button size="small" icon={<CopyOutlined />} onClick={() => { navigator.clipboard.writeText(report); message.success('已复制') }}>
                复制报销单
              </Button>
              <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-lg">{report}</pre>
            </div>
          )}
        </Spin>
      </div>
    </div>
  )
}
