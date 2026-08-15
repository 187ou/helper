import { useState, useEffect } from 'react'
import { Card, Switch, TimePicker, List, Tag, InputNumber, message, Tooltip } from 'antd'
import { ClockCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

interface ScheduleItem {
  key: string
  name: string
  description: string
  enabled: boolean
  time: string
  category: 'work' | 'health' | 'finance'
}

const DEFAULT_SCHEDULES: ScheduleItem[] = [
  { key: 'morning_push', name: '早间推送', description: '每天早 8:00 推送当日工作清单', enabled: true, time: '08:00', category: 'work' },
  { key: 'evening_archive', name: '下班归档', description: '每天晚 18:00 自动归档当日资料', enabled: true, time: '18:00', category: 'work' },
  { key: 'monthly_summary', name: '月末汇总', description: '每月最后一个工作日汇总月度数据', enabled: true, time: '17:00', category: 'work' },
  { key: 'sedentary', name: '久坐提醒', description: '定时提醒起身活动', enabled: true, time: '00:00', category: 'health' },
  { key: 'drink_water', name: '喝水提醒', description: '定时提醒补充水分', enabled: true, time: '00:00', category: 'health' },
  { key: 'finance_review', name: '记账复盘', description: '每周日复盘本周消费', enabled: false, time: '20:00', category: 'finance' },
]

const CATEGORY_COLOR: Record<string, string> = {
  work: 'blue', health: 'green', finance: 'orange',
}

export default function ScheduleConfig() {
  const [schedules, setSchedules] = useState<ScheduleItem[]>(DEFAULT_SCHEDULES)
  const [intervals, setIntervals] = useState<Record<string, number>>({
    sedentary: 60,
    drink_water: 45,
  })

  function toggle(key: string, enabled: boolean) {
    setSchedules((list) =>
      list.map((s) => (s.key === key ? { ...s, enabled } : s)),
    )
  }

  function changeTime(key: string, time: dayjs.Dayjs | null) {
    setSchedules((list) =>
      list.map((s) => (s.key === key ? { ...s, time: time ? time.format('HH:mm') : s.time } : s)),
    )
  }

  function changeInterval(key: string, val: number | null) {
    if (val) setIntervals((prev) => ({ ...prev, [key]: val }))
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
          renderItem={(item) => (
            <List.Item
              actions={[
                <Switch
                  size="small"
                  checked={item.enabled}
                  onChange={(v) => toggle(item.key, v)}
                />,
              ]}
            >
              <List.Item.Meta
                title={<span className="text-sm">{item.name}</span>}
                description={
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500">{item.description}</span>
                    {item.category === 'health' && item.key in intervals ? (
                      <InputNumber
                        size="small"
                        min={10}
                        max={180}
                        value={intervals[item.key]}
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
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">定时配置</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          配置自动事务调度规则，所有定时任务纯本地运行
        </p>
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
