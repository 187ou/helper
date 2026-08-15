import { useState, useEffect } from 'react'
import {
  Card, Row, Col, Statistic, Button, Input, InputNumber, Select, Table, Tag,
  Segmented, Space, Empty, Spin, Popconfirm, DatePicker, message,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, TrendingUpOutlined, TrendingDownOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'

export default function Ledger() {
  const [bills, setBills] = useState<any[]>([])
  const [summary, setSummary] = useState<any>({})
  const [categoryData, setCategoryData] = useState<Record<string, number>>({})
  const [trend, setTrend] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [month, setMonth] = useState(dayjs().format('YYYY-MM'))

  // 新增表单
  const [form, setForm] = useState({ bill_type: 'expense', amount: 0, category: '', description: '', bill_date: dayjs().format('YYYY-MM-DD') })

  const load = async () => {
    setLoading(true)
    try {
      const [list, sum, cat, tr] = await Promise.all([
        api.getBills(month),
        api.getBillSummary(month),
        api.getBillCategory(month),
        api.getBillTrend(6),
      ])
      setBills(list)
      setSummary(sum)
      setCategoryData(cat)
      setTrend(tr)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [month])

  async function addBill() {
    if (!form.amount || form.amount <= 0) {
      message.warning('请输入金额')
      return
    }
    await api.addBill(form)
    message.success('已添加')
    setForm({ ...form, amount: 0, description: '' })
    load()
  }

  async function deleteBill(id: number) {
    await api.deleteBill(id)
    message.success('已删除')
    load()
  }

  const columns = [
    { title: '日期', dataIndex: 'bill_date', width: 120 },
    {
      title: '类型', dataIndex: 'bill_type', width: 80,
      render: (t: string) => <Tag color={t === 'income' ? 'green' : 'orange'}>{t === 'income' ? '收入' : '支出'}</Tag>,
    },
    { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => c || '—' },
    { title: '金额', dataIndex: 'amount', width: 100, render: (a: number) => `¥${a.toFixed(2)}` },
    { title: '备注', dataIndex: 'description', render: (d: string) => d || '—' },
    {
      title: '操作', width: 80,
      render: (_: any, row: any) => (
        <Popconfirm title="确认删除？" onConfirm={() => deleteBill(row.id)}>
          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* 统计 */}
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="本月收入" value={summary.income || 0} precision={2} prefix="¥" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="本月支出" value={summary.expense || 0} precision={2} prefix="¥" valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="结余" value={(summary.income || 0) - (summary.expense || 0)} precision={2} prefix="¥" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="记录数" value={summary.count || 0} suffix="笔" />
          </Card>
        </Col>
      </Row>

      {/* 趋势图（简化版柱状图） */}
      <Card size="small" title="近 6 月收支趋势" className="glass">
        <div className="flex items-end gap-2 h-24">
          {trend.map((t) => {
            const maxVal = Math.max(...trend.map((x) => Math.max(x.income, x.expense)), 1)
            return (
              <div key={t.month} className="flex-1 flex flex-col items-center gap-1">
                <div className="flex gap-0.5 items-end h-16">
                  <div className="w-3 bg-green-400 rounded-t" style={{ height: `${(t.income / maxVal) * 100}%` }} title={`收入 ${t.income}`} />
                  <div className="w-3 bg-orange-400 rounded-t" style={{ height: `${(t.expense / maxVal) * 100}%` }} title={`支出 ${t.expense}`} />
                </div>
                <span className="text-[10px] text-gray-400">{t.month.slice(5)}</span>
              </div>
            )
          })}
        </div>
        <div className="flex gap-4 mt-2 text-xs text-gray-400">
          <span><span className="inline-block w-2 h-2 bg-green-400 rounded mr-1" />收入</span>
          <span><span className="inline-block w-2 h-2 bg-orange-400 rounded mr-1" />支出</span>
        </div>
      </Card>

      {/* 新增 + 筛选 */}
      <Card size="small" className="glass">
        <Space wrap>
          <Select value={form.bill_type} onChange={(v) => setForm({ ...form, bill_type: v })} style={{ width: 90 }}>
            <Select.Option value="expense">支出</Select.Option>
            <Select.Option value="income">收入</Select.Option>
          </Select>
          <InputNumber min={0} step={0.01} value={form.amount} onChange={(v) => setForm({ ...form, amount: v || 0 })} placeholder="金额" style={{ width: 100 }} />
          <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="分类" style={{ width: 100 }} />
          <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="备注" style={{ width: 150 }} />
          <DatePicker value={dayjs(form.bill_date)} onChange={(d) => d && setForm({ ...form, bill_date: d.format('YYYY-MM-DD') })} format="YYYY-MM-DD" />
          <Button type="primary" icon={<PlusOutlined />} onClick={addBill}>添加</Button>
          <Segmented value={month} onChange={(v) => setMonth(v as string)}
            options={Array.from({ length: 6 }, (_, i) => {
              const m = dayjs().subtract(i, 'month')
              return { label: m.format('YYYY-MM'), value: m.format('YYYY-MM') }
            })}
          />
        </Space>
      </Card>

      {/* 分类统计 */}
      {Object.keys(categoryData).length > 0 && (
        <Card size="small" title="支出分类" className="glass">
          <div className="flex flex-wrap gap-2">
            {Object.entries(categoryData).map(([cat, amount]) => (
              <Tag key={cat} color="blue">{cat}: ¥{amount.toFixed(2)}</Tag>
            ))}
          </div>
        </Card>
      )}

      {/* 账单列表 */}
      <Card className="glass flex-1">
        <Spin spinning={loading}>
          <Table dataSource={bills} columns={columns} rowKey="id" size="small" pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="暂无记录" /> }} />
        </Spin>
      </Card>
    </div>
  )
}

import { api } from '../../api'
