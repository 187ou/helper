import { useState, useEffect } from 'react'
import {
  Card, Row, Col, Statistic, Switch, InputNumber, Input, Button, message, Tag, Space,
  Empty,
} from 'antd'
import {
  HeartOutlined, ThunderboltOutlined, BulbOutlined, MoonOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

export default function Health() {
  const [reminders, setReminders] = useState<any>({})
  const [stats, setStats] = useState<any>({})
  const [recordForm, setRecordForm] = useState({ type: 'water', value: 1, note: '' })

  const load = async () => {
    const [r, s] = await Promise.all([api.getHealthReminders(), api.getHealthStats()])
    setReminders(r)
    setStats(s)
  }

  useEffect(() => { load() }, [])

  async function toggleReminder(key: string, field: string, val: any) {
    await api.updateHealthReminders({ [key]: { [field]: val } })
    message.success('已更新')
    load()
  }

  async function addRecord() {
    await api.addHealthRecord({
      record_type: recordForm.type,
      value: recordForm.value,
      note: recordForm.note,
    })
    message.success('已记录')
    load()
  }

  return (
    <div className="flex flex-col gap-4">
      {/* 今日统计 */}
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="今日睡眠" value={stats.today?.sleep || 0} suffix="小时" prefix={<MoonOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="今日饮水" value={stats.today?.water || 0} suffix="杯" prefix={<BulbOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="今日运动" value={stats.today?.exercise || 0} suffix="分钟" prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic title="7 日均眠" value={stats.avg_sleep_7d || 0} suffix="小时" prefix={<HeartOutlined />} />
          </Card>
        </Col>
      </Row>

      {/* 提醒配置 */}
      <Card size="small" title="提醒设置" className="glass">
        <div className="space-y-3">
          {Object.entries(reminders).map(([key, cfg]: [string, any]) => (
            <div key={key} className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">{cfg.title || key}</span>
              </div>
              <Space>
                <InputNumber
                  size="small"
                  min={5} max={180}
                  value={cfg.interval_min}
                  onChange={(v) => v && toggleReminder(key, 'interval_min', v)}
                  addonAfter="分钟"
                  disabled={!cfg.enabled}
                  style={{ width: 120 }}
                />
                <Switch
                  size="small"
                  checked={cfg.enabled}
                  onChange={(v) => toggleReminder(key, 'enabled', v)}
                />
              </Space>
            </div>
          ))}
        </div>
      </Card>

      {/* 快速记录 */}
      <Card size="small" title="快速记录" className="glass">
        <Space wrap>
          <Select value={recordForm.type} onChange={(v) => setRecordForm({ ...recordForm, type: v })} style={{ width: 100 }}>
            <Select.Option value="water">饮水</Select.Option>
            <Select.Option value="sleep">睡眠</Select.Option>
            <Select.Option value="exercise">运动</Select.Option>
            <Select.Option value="weight">体重</Select.Option>
          </Select>
          <InputNumber min={0} value={recordForm.value} onChange={(v) => setRecordForm({ ...recordForm, value: v || 0 })} placeholder="数值" style={{ width: 100 }} />
          <Input value={recordForm.note} onChange={(e) => setRecordForm({ ...recordForm, note: e.target.value })} placeholder="备注" style={{ width: 150 }} />
          <Button type="primary" onClick={addRecord}>记录</Button>
        </Space>
      </Card>

      <div className="text-xs text-gray-400">
        💡 提醒由本地调度器触发，数据完全本地存储
      </div>
    </div>
  )
}
