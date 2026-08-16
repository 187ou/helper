import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Statistic, Progress, Segmented, List, Tag, Button,
  Input, Select, Space, Empty, Spin, Alert, Tooltip,
} from 'antd'
import {
  CheckCircleTwoTone, ClockCircleTwoTone, RiseOutlined,
  PlusOutlined, SearchOutlined, BulbOutlined, ThunderboltOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import { api } from '../api'

interface Stats {
  total: number
  todo: number
  doing: number
  done: number
  archived: number
  due_today: number
  completion_rate: number
  by_type: Record<string, number>
}

interface Task {
  id: number
  task_content: string
  task_type: string
  status: string
  priority: string
  deadline: string
  tags: string
  create_time: string
}

const STATUS_LABELS: Record<string, string> = {
  todo: '待办', doing: '进行中', done: '已完成', failed: '失败', archived: '归档', shelved: '搁置',
}
const PRIORITY_COLOR: Record<string, string> = {
  high: 'red', medium: 'orange', low: 'blue',
}
const TYPE_ICON: Record<string, string> = {
  work: '💼', life: '🏠', health: '💪', mix: '🔀',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [view, setView] = useState('today')
  const [filterType, setFilterType] = useState('all')
  const [loading, setLoading] = useState(true)
  const [quickTitle, setQuickTitle] = useState('')
  const [quickType, setQuickType] = useState('work')
  // 演化洞察
  const [evoReport, setEvoReport] = useState<any>(null)
  const [recommendedTpl, setRecommendedTpl] = useState<any>(null)
  const [proactiveTip, setProactiveTip] = useState<string | null>(null)
  const [emotionTrend, setEmotionTrend] = useState<any>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statsRes, tasksRes, report, tip, emotion] = await Promise.all([
        api.getTaskStats(),
        api.getTasks('?limit=50'),
        api.getLatestReport('daily').catch(() => null),
        api.getProactiveSuggestion().catch(() => null),
        api.getEmotionTrend(7).catch(() => null),
      ])
      setStats(statsRes)
      setTasks(tasksRes)
      setEvoReport(report)
      if (tip?.has_suggestion) setProactiveTip(tip.suggestion)
      setEmotionTrend(emotion)
    } finally {
      setLoading(false)
    }
  }, [])

  // 加载推荐模板
  const loadRecommendation = useCallback(async () => {
    try {
      const rec = await api.recommendTemplate('周报', 'work')
      setRecommendedTpl(rec)
    } catch {
      // 忽略
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadRecommendation() }, [loadRecommendation])

  async function quickAdd() {
    if (!quickTitle.trim()) return
    await api.createTask({
      content: quickTitle.trim(),
      task_type: quickType,
      priority: 'medium',
    })
    setQuickTitle('')
    load()
  }

  // 根据视图过滤任务
  const today = new Date().toISOString().slice(0, 10)
  const weekEnd = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)

  let filtered = tasks.filter((t) => t.status !== 'archived')
  if (filterType !== 'all') {
    filtered = filtered.filter((t) => t.task_type === filterType)
  }
  if (view === 'today') {
    filtered = filtered.filter((t) => !t.deadline || t.deadline <= today || t.status === 'doing')
  } else if (view === 'week') {
    filtered = filtered.filter((t) => !t.deadline || t.deadline <= weekEnd)
  } else if (view === 'todo') {
    filtered = filtered.filter((t) => t.status === 'todo')
  }

  const workItems = filtered.filter((t) => t.task_type === 'work')
  const lifeItems = filtered.filter((t) => t.task_type === 'life')
  const healthItems = filtered.filter((t) => t.task_type === 'health' || t.task_type === 'mix')

  // 演化洞察摘要
  const evoHighlights = evoReport?.content?.highlights || []
  const evoSuggestions = evoReport?.content?.suggestions || []
  const scoreTrend = evoReport?.content?.score_trend

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">工作台看板</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          聚合工作 · 生活 · 健康全量待办，掌握每日事务全貌
        </p>
      </div>

      {/* 智能感知栏（体现记忆系统） */}
      {!loading && (proactiveTip || emotionTrend?.dominant_label) && (
        <div className="flex gap-3">
          {proactiveTip && (
            <Card className="glass flex-1" size="small">
              <div className="flex items-center gap-2">
                <span className="text-base">💡</span>
                <div>
                  <div className="text-xs font-medium text-gray-700">智能建议</div>
                  <div className="text-xs text-gray-500">{proactiveTip}</div>
                </div>
              </div>
            </Card>
          )}
          {emotionTrend?.dominant_label && (
            <Card className="glass flex-1" size="small">
              <div className="flex items-center gap-2">
                <span className="text-base">
                  {emotionTrend.dominant_emotion === 'positive' ? '😊' :
                   emotionTrend.dominant_emotion === 'negative' ? '😤' :
                   emotionTrend.dominant_emotion === 'anxious' ? '😰' :
                   emotionTrend.dominant_emotion === 'bored' ? '😑' : '😐'}
                </span>
                <div>
                  <div className="text-xs font-medium text-gray-700">情绪状态</div>
                  <div className="text-xs text-gray-500">
                    {emotionTrend.dominant_label}
                    {emotionTrend.trend && ` · ${emotionTrend.trend}`}
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* 演化洞察 + 推荐 */}
      {!loading && (evoHighlights.length > 0 || recommendedTpl?.steps) && (
        <Row gutter={16}>
          {evoHighlights.length > 0 && (
            <Col span={12}>
              <Card
                size="small"
                title={<span><ExperimentOutlined /> 演化洞察</span>}
                className="glass"
                extra={<Button size="small" type="link" onClick={() => navigate('/evolution')}>详情</Button>}
              >
                <List
                  size="small"
                  dataSource={evoHighlights.slice(0, 3)}
                  renderItem={(item) => (
                    <List.Item className="py-1">
                      <span className="text-xs text-gray-600">💡 {item}</span>
                    </List.Item>
                  )}
                />
                {scoreTrend?.trend && (
                  <div className="mt-2 text-xs text-gray-500">
                    分数趋势: <Tag color={scoreTrend.trend === 'improving' ? 'green' : scoreTrend.trend === 'declining' ? 'red' : 'blue'}>
                      {scoreTrend.trend === 'improving' ? '上升' : scoreTrend.trend === 'declining' ? '下降' : '稳定'}
                    </Tag>
                  </div>
                )}
              </Card>
            </Col>
          )}
          {recommendedTpl?.steps && (
            <Col span={12}>
              <Card
                size="small"
                title={<span><BulbOutlined /> 推荐模板</span>}
                className="glass"
                extra={<Button size="small" type="link" onClick={() => navigate('/templates')}>更多</Button>}
              >
                <div className="text-xs text-gray-500 mb-2">
                  基于您的使用习惯，推荐以下模板（来源: {recommendedTpl.source}）
                </div>
                <List
                  size="small"
                  dataSource={recommendedTpl.steps.slice(0, 3)}
                  renderItem={(item, i) => (
                    <List.Item className="py-1">
                      <span className="text-xs text-gray-600">{i + 1}. {item.name || item}</span>
                    </List.Item>
                  )}
                />
                <Button
                  size="small"
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  className="mt-2"
                  onClick={async () => {
                    await api.createTask({
                      content: '执行推荐模板',
                      task_type: 'work',
                      priority: 'medium',
                      steps: recommendedTpl.steps,
                      source: 'recommendation',
                    })
                    navigate('/tasks')
                  }}
                >
                  一键启动
                </Button>
              </Card>
            </Col>
          )}
        </Row>
      )}

      {/* 统计卡片 */}
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic
              title="待办总数"
              value={stats?.total ?? 0}
              prefix={<ClockCircleTwoTone />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic
              title="已完成"
              value={stats?.done ?? 0}
              prefix={<CheckCircleTwoTone twoToneColor="#52c41a" />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <Statistic
              title="今日到期"
              value={stats?.due_today ?? 0}
              prefix={<RiseOutlined />}
              valueStyle={{ color: (stats?.due_today ?? 0) > 0 ? '#ff4d4f' : undefined }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="glass">
            <div className="text-xs text-gray-500 mb-1">完成率</div>
            <Progress
              type="circle"
              percent={stats?.completion_rate ?? 0}
              size={56}
              format={(p) => `${p}%`}
            />
          </Card>
        </Col>
      </Row>

      {/* 快速添加 + 视图切换 */}
      <div className="flex items-center gap-3">
        <Input
          placeholder="快速添加任务，回车确认..."
          value={quickTitle}
          onChange={(e) => setQuickTitle(e.target.value)}
          onPressEnter={quickAdd}
          prefix={<SearchOutlined />}
          className="flex-1"
        />
        <Select value={quickType} onChange={setQuickType} style={{ width: 100 }}>
          <Select.Option value="work">💼 工作</Select.Option>
          <Select.Option value="life">🏠 生活</Select.Option>
          <Select.Option value="health">💪 健康</Select.Option>
        </Select>
        <Button type="primary" icon={<PlusOutlined />} onClick={quickAdd}>
          添加
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { label: '今日视图', value: 'today' },
            { label: '本周视图', value: 'week' },
            { label: '清单视图', value: 'list' },
            { label: '时间线', value: 'timeline' },
          ]}
        />
        <Select value={filterType} onChange={setFilterType} style={{ width: 120 }}>
          <Select.Option value="all">全部分类</Select.Option>
          <Select.Option value="work">💼 工作</Select.Option>
          <Select.Option value="life">🏠 生活</Select.Option>
          <Select.Option value="health">💪 健康</Select.Option>
        </Select>
      </div>

      {/* 三分类卡片 */}
      <Spin spinning={loading}>
        {view === 'timeline' ? (
          <Card size="small" title="📅 时间线" className="glass">
            <List
              dataSource={filtered.sort((a, b) => (a.deadline || '').localeCompare(b.deadline || ''))}
              locale={{ empty: <Empty description="暂无任务" /> }}
              renderItem={(item) => (
                <List.Item>
                  <div className="flex items-center gap-2 w-full">
                    <Tag color={PRIORITY_COLOR[item.priority]}>{item.priority}</Tag>
                    <span className="text-xs text-gray-400">{item.deadline || '无截止'}</span>
                    <span className="flex-1">{item.task_content}</span>
                    <Tag>{STATUS_LABELS[item.status]}</Tag>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        ) : (
          <Row gutter={16} className="flex-1">
            <Col span={8}>
              <Card
                size="small"
                title={<span>💼 工作待办 <span className="text-gray-400 text-xs">({workItems.length})</span></span>}
                className="glass h-full"
              >
                <List
                  dataSource={workItems}
                  locale={{ empty: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无" /> }}
                  renderItem={(item) => (
                    <List.Item className="flex items-center gap-2">
                      <span className="flex-1 truncate">{item.task_content}</span>
                      <Tag color={PRIORITY_COLOR[item.priority]} className="text-xs">{item.priority}</Tag>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card
                size="small"
                title={<span>🏠 生活待办 <span className="text-gray-400 text-xs">({lifeItems.length})</span></span>}
                className="glass h-full"
              >
                <List
                  dataSource={lifeItems}
                  locale={{ empty: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无" /> }}
                  renderItem={(item) => (
                    <List.Item className="flex items-center gap-2">
                      <span className="flex-1 truncate">{item.task_content}</span>
                      <Tag color={PRIORITY_COLOR[item.priority]} className="text-xs">{item.priority}</Tag>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card
                size="small"
                title={<span>💪 健康提醒 <span className="text-gray-400 text-xs">({healthItems.length})</span></span>}
                className="glass h-full"
              >
                <List
                  dataSource={healthItems}
                  locale={{ empty: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无" /> }}
                  renderItem={(item) => (
                    <List.Item className="flex items-center gap-2">
                      <span className="flex-1 truncate">{item.task_content}</span>
                      <Tag color={PRIORITY_COLOR[item.priority]} className="text-xs">{item.priority}</Tag>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
          </Row>
        )}
      </Spin>
    </div>
  )
}
