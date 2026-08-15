import { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Statistic, Segmented, List, Tag, Button, Progress,
  Timeline, Empty, Spin, Tooltip, Collapse, Badge, message,
} from 'antd'
import {
  AimOutlined, ThunderboltOutlined, RobotOutlined, FireOutlined,
  ReloadOutlined, DeleteOutlined, InfoCircleOutlined,
} from '@ant-design/icons'
import { api } from '../api'

interface EvoLog {
  id: number
  evo_type: string
  before_content: string
  after_content: string
  evo_time: string
}
interface Weight {
  habit_key: string
  weight: number
  freq_count: number
  last_use_time: string
}
interface BehaviorStats {
  total: number
  by_type: Record<string, number>
  daily_active: { date: string; count: number }[]
}

const TYPE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  flow: { label: '流程优化', color: 'blue', icon: '⚡' },
  weight: { label: '权重迭代', color: 'green', icon: '🧠' },
  template: { label: '模板固化', color: 'purple', icon: '📐' },
  tool: { label: '工具新增', color: 'orange', icon: '🧰' },
}

export default function Evolution() {
  const [stats, setStats] = useState<Record<string, number>>({})
  const [logs, setLogs] = useState<EvoLog[]>([])
  const [weights, setWeights] = useState<Weight[]>([])
  const [behaviorStats, setBehaviorStats] = useState<BehaviorStats | null>(null)
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, w, b] = await Promise.all([
        api.getStats(),
        api.getWeights(),
        api.getBehaviorStats(),
      ])
      setStats(s)
      setWeights(w)
      setBehaviorStats(b)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const type = filter === 'all' ? '' : filter
    api.getLogs(type).then(setLogs)
  }, [filter])

  async function clearBehavior() {
    const res = await api.logBehavior('clear', {})  // 触发行为记录
    message.success('行为采集已记录')
  }

  // 计算平均权重
  const avgWeight = weights.length > 0
    ? (weights.reduce((a, w) => a + w.weight, 0) / weights.length).toFixed(1)
    : '0'

  // 最大频次（用于热力图归一化）
  const maxDaily = behaviorStats?.daily_active
    ? Math.max(...behaviorStats.daily_active.map((d) => d.count), 1)
    : 1

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">进化中心</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            自适应演化引擎 · 系统自我优化记录 · 记忆权重分布
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16}>
        <Col span={4}>
          <Card size="small" className="glass">
            <Statistic title="流程优化" value={stats.flow_optimizations || 0} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" className="glass">
            <Statistic title="固化模板" value={stats.template_count || 0} prefix={<AimOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" className="glass">
            <Statistic title="演化工具" value={stats.tool_count || 0} prefix={<RobotOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" className="glass">
            <Statistic title="权重习惯" value={weights.length} prefix={<FireOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" className="glass">
            <Statistic title="平均权重" value={avgWeight} suffix="/ 10" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" className="glass">
            <Statistic title="行为记录" value={behaviorStats?.total || 0} />
          </Card>
        </Col>
      </Row>

      {/* 行为活跃度热力图 */}
      <Card
        size="small"
        title={<span>📊 近 7 天行为活跃度</span>}
        className="glass"
        extra={
          <Tooltip title="记录用户操作频率，为演化提供数据源">
            <InfoCircleOutlined className="text-gray-400" />
          </Tooltip>
        }
      >
        {behaviorStats?.daily_active && behaviorStats.daily_active.length > 0 ? (
          <div className="flex items-end gap-1 h-16">
            {behaviorStats.daily_active.map((d) => (
              <Tooltip key={d.date} title={`${d.date}: ${d.count} 次操作`}>
                <div className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-t bg-gradient-to-t from-indigo-500 to-purple-400 transition-all"
                    style={{ height: `${Math.max((d.count / maxDaily) * 100, 8)}%` }}
                  />
                  <span className="text-[10px] text-gray-400">{d.date.slice(5)}</span>
                </div>
              </Tooltip>
            ))}
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" className="py-2" />
        )}
      </Card>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* 演化时间轴 */}
        <Card
          size="small"
          title="📜 演化时间轴"
          className="glass flex-1 flex flex-col"
          extra={
            <Segmented
              size="small"
              value={filter}
              onChange={setFilter}
              options={[
                { label: '全部', value: 'all' },
                { label: '优化', value: 'flow' },
                { label: '权重', value: 'weight' },
                { label: '模板', value: 'template' },
              ]}
            />
          }
        >
          <Spin spinning={loading}>
            <List
              dataSource={logs}
              locale={{ empty: <Empty description="暂无演化记录" /> }}
              renderItem={(log) => {
                const cfg = TYPE_CONFIG[log.evo_type] || { label: log.evo_type, color: 'default', icon: '📝' }
                return (
                  <List.Item>
                    <div className="w-full">
                      <div className="flex items-center gap-2 mb-1">
                        <Tag color={cfg.color}>{cfg.icon} {cfg.label}</Tag>
                        <span className="text-xs text-gray-400">{log.evo_time}</span>
                      </div>
                      {log.evo_type === 'flow' ? (
                        <Collapse
                          size="small"
                          items={[{
                            key: String(log.id),
                            label: '查看优化前后对比',
                            children: (
                              <div className="text-xs space-y-1">
                                <div className="text-red-500 line-through opacity-70">❌ {log.before_content}</div>
                                <div className="text-green-600">✅ {log.after_content}</div>
                              </div>
                            ),
                          }]}
                        />
                      ) : (
                        <div className="text-xs text-gray-600">
                          {log.before_content} → {log.after_content}
                        </div>
                      )}
                    </div>
                  </List.Item>
                )
              }}
            />
          </Spin>
        </Card>

        {/* 记忆权重 */}
        <Card
          size="small"
          title="🧠 记忆权重分布"
          className="glass w-80 flex flex-col"
          extra={
            <Tooltip title="高频习惯自动提权，长期不用自动衰减">
              <InfoCircleOutlined className="text-gray-400" />
            </Tooltip>
          }
        >
          <div className="flex-1 overflow-y-auto space-y-3">
            {weights.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无权重数据" />}
            {weights.map((w) => (
              <div key={w.habit_key}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium">{w.habit_key}</span>
                  <span className="text-gray-400">
                    <Badge count={w.freq_count} size="small" color="#6366f1" /> {w.weight.toFixed(1)}
                  </span>
                </div>
                <Progress
                  percent={Math.min(Math.round(w.weight * 10), 100)}
                  showInfo={false}
                  strokeColor={w.weight >= 7 ? '#52c41a' : w.weight >= 4 ? '#6366f1' : '#d9d9d9'}
                  size="small"
                />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
