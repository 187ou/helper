import { useState, useEffect } from 'react'
import { Card, Switch, TimePicker, List, Tag, InputNumber, message, Tooltip, Button, Space } from 'antd'
import { ClockCircleOutlined, InfoCircleOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../api'

interface ScheduleItem {
  key: string
  name: string
  description: string
  enabled: boolean
  time: string
  category: 'work' | 'health' | 'finance'
  interval_min?: number
}

const DEFAULT_SCHEDULES: ScheduleItem[] = [
  { key: 'morning_push', name: '早间推送', description: '每天早 8:00 推送当日工作清单', enabled: true, time: '08:00', category: 'work' },
  { key: 'evening_archive', name: '下班归档', description: '每天晚 18:00 自动归档当日资料', enabled: true, time: '18:00', category: 'work' },
  { key: 'monthly_summary', name: '月末汇总', description: '每月最后一个工作日汇总月度数据', enabled: true, time: '17:00', category: 'work' },
  { key: 'sedentary', name: '久坐提醒', description: '定时提醒起身活动', enabled: true, time: '00:00', category: 'health', interval_min: 60 },
  { key: 'drink_water', name: '喝水提醒', description: '定时提醒补充水分', enabled: true, time: '00:00', category: 'health', interval_min: 45 },
  { key: 'finance_review', name: '记账复盘', description: '每周日复盘本周消费', enabled: false, time: '20:00', category: 'finance' },
]

const CATEGORY_COLOR: Record<string, string> = {
  work: 'blue', health: 'green', finance: 'orange',
}

export default function ScheduleConfig() {
  const [schedules, setSchedules] = useState<ScheduleItem[]>(DEFAULT_SCHEDULES)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // 加载后端配置
  useEffect(() => {
    loadConfig()
  }, [])

  async function loadConfig() {
    setLoading(true)
    try {
      // 加载健康提醒配置
      const reminders = await api.getHealthReminders()
      if (reminders && reminders.length > 0) {
        setSchedules((prev) =>
          prev.map((s) => {
            const r = reminders.find((rm: any) => rm.type === s.key)
            if (r) {
              return {
                ...s,
                enabled: r.enabled,
                interval_min: r.interval_min || s.interval_min,
              }
            }
            return s
          })
        )
      }
    } catch (e) {
      // 使用默认配置
    } finally {
      setLoading(false)
    }
  }

  async function saveConfig() {
    setSaving(true)
    try {
      // 保存健康提醒配置
      const healthConfigs = schedules
        .filter((s) => s.category === 'health')
        .reduce((acc, s) => {
          acc[s.key] = { enabled: s.enabled, interval_min: s.interval_min }
          return acc
        }, {} as Record<string, any>)

      await api.updateHealthReminders(healthConfigs)
      message.success('配置已保存')
    } catch (e) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  function toggle(key: string, enabled: boolean) {
    setSchedules((list) => list.map((s) => (s.key === key ? { ...s, enabled } : s)))
  }

  function changeTime(key: string, time: dayjs.Dayjs | null) {
    setSchedules((list) => list.map((s) => (s.key === key ? { ...s, time: time ? time.format('HH:mm') : s.time } : s)))
  }

  function changeInterval(key: string, val: number | null) {
    setSchedules((list) => list.map((s) => (s.key === key ? { ...s, interval_min: val || s.interval_min } : s)))
  }

  const workItems = schedules.filter((s) => s.category === 'work')
  const healthItems = schedules.filter((s) => s.category === 'health')
  const financeItems = schedules.filter((s) => s.category === 'finance')

  function renderList(title: string, items: ScheduleItem[]) {
    return (
      <Card
        size="small"
        title={title}
        className="glass"
        extra={<Tag color={CATEGORY_COLOR[items[0]?.category]}>{items.length} 项</Tag>}
      >
        <List
          dataSource={items}
          loading={loading}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Switch size="small" checked={item.enabled} onChange={(v) => toggle(item.key, v)} />,
              ]}
            >
              <List.Item.Meta
                title={<span className="text-sm">{item.name}</span>}
                description={
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500">{item.description}</span>
                    {item.interval_min != null ? (
                      <InputNumber
                        size="small"
                        min={10}
                        max={180}
                        value={item.interval_min}
                        onChange={(v) => changeInterval(item.key, v)}
                        addonAfter="分钟"
                        disabled={!item.enabled}
                        style={{ width: 120 }}
                      />
                    ) : (
                      <TimePicker
                        size="small"
                        format="HH:mm"
                        value={dayjs(item.time, 'HH:mm')}
                        onChange={(t) => changeTime(item.key, t)}
                        disabled={!item.enabled}
                        style={{ width: 100 }}
                      />
                    )}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    )
  }

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">定时配置</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            配置自动事务调度规则，所有定时任务纯本地运行
          </p>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadConfig}>刷新</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveConfig}>
            保存配置
          </Button>
        </Space>
      </div>

      <Card size="small" className="glass" type="inner">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <InfoCircleOutlined />
          <span>定时任务由本地调度器准时触发，重启后自动恢复。健康提醒间隔以分钟计。</span>
        </div>
      </Card>

      {renderList('💼 工作调度', workItems)}
      {renderList('💪 健康提醒', healthItems)}
      {renderList('💰 财务复盘', financeItems)}
    </div>
  )
}
