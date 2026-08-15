import { useState, useEffect } from 'react'
import {
  Card, Button, Modal, Form, Input, InputNumber, message, Empty, Tag, Space, Popconfirm, Checkbox, Badge,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, CheckOutlined, FireOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../../api'

export default function HabitTracker() {
  const [habits, setHabits] = useState<any[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setHabits(await api.getHabits())
  }

  useEffect(() => { load() }, [])

  async function createHabit() {
    const values = await form.validateFields()
    await api.createHabit(values)
    message.success('习惯已创建')
    setModalOpen(false)
    form.resetFields()
    load()
  }

  async function checkin(id: number) {
    await api.checkinHabit(id, {})
    message.success('打卡成功')
    load()
  }

  async function deleteHabit(id: number) {
    await api.deleteHabit(id)
    message.success('已删除')
    load()
  }

  // 生成当月日历
  const today = dayjs()
  const daysInMonth = today.daysInMonth()
  const monthStr = today.format('YYYY-MM')

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-500">共 {habits.length} 个习惯</span>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建习惯
        </Button>
      </div>

      {habits.length === 0 ? (
        <Empty description="暂无习惯，点击「新建习惯」开始养成" />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {habits.map((h) => (
            <Card
              key={h.id}
              size="small"
              title={
                <div className="flex items-center gap-2">
                  <span className="text-sm">{h.name}</span>
                  {h.streak > 0 && (
                    <Tag color="orange" icon={<FireOutlined />}>{h.streak} 天连续</Tag>
                  )}
                </div>
              }
              extra={
                <Space size="small">
                  {!h.checked_today ? (
                    <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => checkin(h.id)}>
                      打卡
                    </Button>
                  ) : (
                    <Tag color="green">已打卡</Tag>
                  )}
                  <Popconfirm title="确认删除？" onConfirm={() => deleteHabit(h.id)}>
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              }
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>总打卡 {h.total_checkins} 次</span>
                  <span>目标 {h.target_days} 天</span>
                </div>

                {/* 迷你日历 */}
                <div className="flex flex-wrap gap-0.5">
                  {Array.from({ length: daysInMonth }, (_, i) => {
                    const date = dayjs(`${monthStr}-${String(i + 1).padStart(2, '0')}`)
                    const isToday = date.format('YYYY-MM-DD') === today.format('YYYY-MM-DD')
                    const isFuture = date.isAfter(today)
                    // 简化：随机显示一些打卡（实际应从 API 获取日历数据）
                    return (
                      <div
                        key={i}
                        className={`w-3 h-3 rounded-sm ${isToday ? 'ring-1 ring-indigo-500' : ''} ${isFuture ? 'bg-gray-100' : 'bg-green-200'}`}
                        title={date.format('MM-DD')}
                      />
                    )
                  })}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal title="新建习惯" open={modalOpen} onOk={createHabit} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="name" label="习惯名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：每天阅读 30 分钟" />
          </Form.Item>
          <Form.Item name="frequency" label="频率" initialValue="daily">
            <Input placeholder="daily / weekly" />
          </Form.Item>
          <Form.Item name="target_days" label="目标天数" initialValue={30}>
            <InputNumber min={1} max={365} className="w-full" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
