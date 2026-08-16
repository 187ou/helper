/**
 * 智能提醒页面 —— 体现前瞻记忆能力
 *
 * 功能：
 * 1. 自然语言创建提醒（"下周三提醒我交周报"）
 * 2. 时间触发 / 事件触发 / 条件触发
 * 3. 周期性提醒（每天/每周/每月）
 * 4. 提醒列表管理
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Card, List, Tag, Button, Input, Empty, Spin, Segmented,
  Popconfirm, Tooltip, Badge, message,
} from 'antd'
import {
  BellOutlined, ClockCircleOutlined, ThunderboltOutlined,
  DeleteOutlined, CheckOutlined, CloseOutlined,
  PlusOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { api } from '../api'

const TRIGGER_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  time: { label: '时间', color: 'blue', icon: '⏰' },
  event: { label: '事件', color: 'green', icon: '⚡' },
  condition: { label: '条件', color: 'orange', icon: '🔔' },
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: '待触发', color: 'default' },
  triggered: { label: '已触发', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  dismissed: { label: '已取消', color: 'default' },
}

export default function Reminders() {
  const [reminders, setReminders] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [inputText, setInputText] = useState('')
  const [filter, setFilter] = useState('pending')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const list = await api.listReminders(filter)
      setReminders(list)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  async function createFromText() {
    if (!inputText.trim()) return
    try {
      const result = await api.parseIntent(inputText)
      if (result.is_intent) {
        message.success(result.message || '提醒已创建')
        setInputText('')
        load()
      } else {
        message.info('未识别到提醒意图，请尝试"记住..."、"提醒..."等表达')
      }
    } catch (e: any) {
      message.error(e.message || '创建失败')
    }
  }

  async function completeReminder(id: number) {
    await api.completeReminder(id)
    message.success('已完成')
    load()
  }

  async function dismissReminder(id: number) {
    await api.dismissReminder(id)
    message.success('已取消')
    load()
  }

  async function deleteReminder(id: number) {
    await api.deleteReminder(id)
    message.success('已删除')
    load()
  }

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">智能提醒</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          自然语言创建提醒 · 时间/事件/条件触发 · 周期性重复
        </p>
      </div>

      {/* 创建提醒 */}
      <Card className="glass" size="small">
        <Input.Search
          placeholder='试试：记住每天早上9点提醒我写日报 / 每次收到发票时提醒我报销 / 连续3天没记账时提醒我'
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onSearch={createFromText}
          enterButton={<span><PlusOutlined /> 创建</span>}
          size="small"
        />
        <div className="flex gap-2 mt-2 flex-wrap">
          <Tag className="cursor-pointer" onClick={() => setInputText('记住明天提醒我')}>明天提醒</Tag>
          <Tag className="cursor-pointer" onClick={() => setInputText('每周五提醒我交周报')}>每周五</Tag>
          <Tag className="cursor-pointer" onClick={() => setInputText('每天早上9点提醒我写日报')}>每天</Tag>
          <Tag className="cursor-pointer" onClick={() => setInputText('每次收到发票时提醒我报销')}>事件触发</Tag>
        </div>
      </Card>

      {/* 筛选 + 列表 */}
      <Card
        className="glass flex-1 flex flex-col"
        size="small"
        title={<span><BellOutlined /> 提醒列表</span>}
        extra={
          <Segmented size="small" value={filter} onChange={setFilter}
            options={[
              { label: '待触发', value: 'pending' },
              { label: '全部', value: 'all' },
            ]}
          />
        }
      >
        <Spin spinning={loading}>
          <List
            dataSource={reminders}
            locale={{ empty: <Empty description="暂无提醒" /> }}
            renderItem={(item) => {
              const triggerCfg = TRIGGER_LABELS[item.trigger_type] || TRIGGER_LABELS.time
              const statusCfg = STATUS_LABELS[item.status] || STATUS_LABELS.pending
              return (
                <List.Item
                  actions={item.status === 'pending' ? [
                    <Tooltip key="complete" title="标记完成">
                      <Button type="link" size="small" icon={<CheckOutlined />}
                        onClick={() => completeReminder(item.id)} />
                    </Tooltip>,
                    <Tooltip key="dismiss" title="取消">
                      <Button type="link" size="small" icon={<CloseOutlined />}
                        onClick={() => dismissReminder(item.id)} />
                    </Tooltip>,
                  ] : [
                    <Popconfirm key="delete" title="删除此提醒？" onConfirm={() => deleteReminder(item.id)}>
                      <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <div className="flex items-center gap-2">
                        <Tag color={triggerCfg.color}>{triggerCfg.icon} {triggerCfg.label}</Tag>
                        <Tag color={statusCfg.color}>{statusCfg.label}</Tag>
                        <span className="text-xs text-gray-600">{item.user_intent || item.note}</span>
                      </div>
                    }
                    description={
                      <div className="text-[10px] text-gray-400">
                        {item.trigger_value && <span>触发: {item.trigger_value} · </span>}
                        {item.recurrence && <span>重复: {item.recurrence} · </span>}
                        创建于 {item.create_time}
                      </div>
                    }
                  />
                </List.Item>
              )
            }}
          />
        </Spin>
      </Card>
    </div>
  )
}
