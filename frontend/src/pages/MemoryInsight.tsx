/**
 * 记忆洞察页面 —— 展现"系统懂你"的核心体验
 *
 * 设计理念：不直接展示"记忆引擎"，而是让用户感受到：
 * 1. 系统知道我的情绪和节奏（情感记忆）
 * 2. 系统理解我的能力和痛点（用户模型）
 * 3. 系统能预测我的需求（主动推理）
 * 4. 系统记得我的故事（长期叙事）
 * 5. 系统在学习我的偏好（反馈闭环）
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Progress, Tag, Button, Spin, Empty, Segmented,
  Statistic, Timeline, Collapse, Tooltip, Badge, message,
} from 'antd'
import {
  HeartOutlined, BulbOutlined, EyeOutlined, FireOutlined,
  ThunderboltOutlined, AimOutlined, ReloadOutlined,
  CheckCircleOutlined, WarningOutlined, RiseOutlined,
  SmileOutlined, FrownOutlined, MehOutlined,
} from '@ant-design/icons'
import { api } from '../api'

export default function MemoryInsight() {
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<any>({})
  const [userModel, setUserModel] = useState<any>({})
  const [emotionTrend, setEmotionTrend] = useState<any>({})
  const [narrative, setNarrative] = useState<any>({})
  const [reflection, setReflection] = useState<any>({})
  const [activeTab, setActiveTab] = useState('overview')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [h, m, e, n, r] = await Promise.all([
        api.getMemoryHealth().catch(() => ({})),
        api.getUserModel().catch(() => ({})),
        api.getEmotionTrend(7).catch(() => ({})),
        api.getNarrative('monthly').catch(() => ({})),
        api.getDeepReflection('weekly').catch(() => ({})),
      ])
      setHealth(h)
      setUserModel(m)
      setEmotionTrend(e)
      setNarrative(n)
      setReflection(r)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const healthScore = health.health_score ?? 0
  const healthColor = healthScore >= 80 ? '#52c41a' : healthScore >= 60 ? '#faad14' : '#ff4d4f'

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">记忆洞察</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            系统如何理解你 · 情感 · 能力 · 偏好 · 故事
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </div>

      <Segmented
        value={activeTab}
        onChange={setActiveTab}
        options={[
          { label: '🧠 概览', value: 'overview' },
          { label: '💝 情感', value: 'emotion' },
          { label: '👤 用户画像', value: 'profile' },
          { label: '📖 我的故事', value: 'story' },
        ]}

      />

      <Spin spinning={loading}>
        {/* ── 概览 Tab ── */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* 记忆健康评分 */}
            <Row gutter={16}>
              <Col span={6}>
                <Card className="glass" size="small">
                  <div className="text-center">
                    <Progress
                      type="dashboard" percent={healthScore}
                      strokeColor={healthColor}
                      format={(p) => <span style={{ fontSize: 28, fontWeight: 600, color: healthColor }}>{p}</span>}
                    />
                    <div className="text-xs text-gray-500 mt-1">记忆健康度</div>
                    <Tag color={healthScore >= 80 ? 'green' : healthScore >= 60 ? 'orange' : 'red'}>
                      {health.status || 'unknown'}
                    </Tag>
                  </div>
                </Card>
              </Col>
              <Col span={6}>
                <Card className="glass" size="small">
                  <Statistic title="总记忆数" value={health.total_memories || 0}
                    prefix={<AimOutlined style={{ color: '#6366f1' }} />} />
                  <div className="text-[10px] text-gray-400 mt-1">
                    类型: {Object.entries(health.type_distribution || {}).map(([k, v]) => `${k}:${v}`).join(', ')}
                  </div>
                </Card>
              </Col>
              <Col span={6}>
                <Card className="glass" size="small">
                  <Statistic title="平均置信度" value={(health.avg_confidence || 0).toFixed(2)}
                    prefix={<EyeOutlined style={{ color: '#52c41a' }} />} />
                  <div className="text-[10px] text-gray-400 mt-1">
                    新鲜度: {Object.entries(health.freshness_distribution || {}).map(([k, v]) => `${k}:${v}`).join(', ')}
                  </div>
                </Card>
              </Col>
              <Col span={6}>
                <Card className="glass" size="small">
                  <Statistic title="冲突记忆" value={health.conflict_count || 0}
                    prefix={<WarningOutlined style={{ color: health.conflict_count > 0 ? '#ff4d4f' : '#52c41a' }} />} />
                  <div className="text-[10px] text-gray-400 mt-1">
                    {health.conflict_count > 0 ? '需要处理冲突' : '无冲突'}
                  </div>
                </Card>
              </Col>
            </Row>

            {/* 个性化问候 */}
            <Card className="glass" size="small" title={<span><SmileOutlined /> 系统眼中的你</span>}>
              {userModel.capability ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Tag color="blue">{userModel.capability.level || 'unknown'}</Tag>
                    <span className="text-sm text-gray-600">{userModel.capability.description}</span>
                  </div>
                  {userModel.rhythm && (
                    <div className="text-xs text-gray-500">
                      🕐 {userModel.rhythm.description}
                      {userModel.rhythm.peak_hours?.length > 0 && (
                        <span className="ml-2">高峰: {userModel.rhythm.peak_hours.join(', ')}</span>
                      )}
                    </div>
                  )}
                  {userModel.current_focus && (
                    <div className="text-xs text-gray-500">
                      🎯 当前关注: {userModel.current_focus.description}
                    </div>
                  )}
                </div>
              ) : (
                <Empty description="数据不足，继续完成任务来建立你的画像" />
              )}
            </Card>

            {/* 最近洞察 */}
            {reflection?.insights?.length > 0 && (
              <Card className="glass" size="small" title={<span><BulbOutlined /> 本周洞察</span>}>
                <ul className="space-y-1">
                  {reflection.insights.slice(0, 3).map((insight: string, i: number) => (
                    <li key={i} className="text-xs text-gray-600 flex items-start gap-1">
                      <span className="text-indigo-500">💡</span> {insight}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}

        {/* ── 情感 Tab ── */}
        {activeTab === 'emotion' && (
          <div className="space-y-4">
            <Card className="glass" size="small" title={<span><HeartOutlined /> 情绪趋势</span>}>
              {emotionTrend.trend_description ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">
                      {emotionTrend.dominant_emotion === 'positive' ? '😊' :
                       emotionTrend.dominant_emotion === 'negative' ? '😤' :
                       emotionTrend.dominant_emotion === 'anxious' ? '😰' :
                       emotionTrend.dominant_emotion === 'bored' ? '😑' : '😐'}
                    </span>
                    <div>
                      <div className="text-sm font-medium">主导情绪: {emotionTrend.dominant_label || '中性'}</div>
                      <div className="text-xs text-gray-500">{emotionTrend.trend_description}</div>
                    </div>
                  </div>
                  {emotionTrend.emotion_distribution && (
                    <div className="flex gap-2 flex-wrap">
                      {Object.entries(emotionTrend.emotion_distribution).map(([k, v]) => (
                        <Tag key={k}>{k}: {v as number}</Tag>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <Empty description="暂无情绪数据，继续与系统互动来记录你的情绪" />
              )}
            </Card>

            {/* 情绪适配建议 */}
            <Card className="glass" size="small" title={<span><ThunderboltOutlined /> 系统如何适配你</span>}>
              <div className="text-xs text-gray-600 space-y-1">
                <p>• 当你情绪积极时，系统会尝试提供进阶功能</p>
                <p>• 当你感到焦虑时，系统会简化输出并提供明确指导</p>
                <p>• 当你感到厌烦时，系统会尝试新的角度或简化流程</p>
                <p>• 负面情绪累积时，系统会主动预警</p>
              </div>
            </Card>
          </div>
        )}

        {/* ── 用户画像 Tab ── */}
        {activeTab === 'profile' && (
          <div className="space-y-4">
            {/* 能力评估 */}
            {userModel.capability?.dimensions && (
              <Card className="glass" size="small" title={<span><FireOutlined /> 能力维度</span>}>
                <Row gutter={16}>
                  {Object.entries(userModel.capability.dimensions).map(([k, v]) => (
                    <Col span={8} key={k}>
                      <div className="text-center">
                        <Progress type="circle" percent={v as number} size={60}
                          strokeColor={v >= 80 ? '#52c41a' : v >= 50 ? '#faad14' : '#ff4d4f'} />
                        <div className="text-[10px] text-gray-500 mt-1">
                          {k === 'completion' ? '完成能力' : k === 'quality' ? '质量能力' : '效率'}
                        </div>
                      </div>
                    </Col>
                  ))}
                </Row>
              </Card>
            )}

            {/* 痛点 */}
            {userModel.pain_points?.length > 0 && (
              <Card className="glass" size="small" title={<span><WarningOutlined /> 发现的痛点</span>}>
                <Timeline
                  items={userModel.pain_points.map((p: any) => ({
                    color: p.type === 'repeated_failure' ? 'red' : 'blue',
                    children: (
                      <div className="text-xs">
                        <div className="font-medium">{p.target}</div>
                        <div className="text-gray-500">{p.suggestion}</div>
                      </div>
                    ),
                  }))}
                />
              </Card>
            )}

            {/* 偏好画像 */}
            {userModel.preference_profile?.top_style_preferences?.length > 0 && (
              <Card className="glass" size="small" title={<span><AimOutlined /> 你的偏好</span>}>
                <div className="space-y-2">
                  {userModel.preference_profile.top_style_preferences.map((p: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-gray-600">{p.key}</span>
                      <span className="flex items-center gap-1">
                        <span>{p.value}</span>
                        <Progress percent={Math.round(p.confidence * 100)} size="small" style={{ width: 80 }}
                          strokeColor="#6366f1" />
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        )}

        {/* ── 故事 Tab ── */}
        {activeTab === 'story' && (
          <div className="space-y-4">
            {/* 一句话故事 */}
            <Card className="glass" size="small" title={<span><RiseOutlined /> 你的故事</span>}>
              <p className="text-sm text-gray-600 italic">
                "{narrative.summary || '继续记录你的故事...'}"
              </p>
            </Card>

            {/* 里程碑 */}
            {narrative.milestones?.length > 0 && (
              <Card className="glass" size="small" title={<span><Badge count={narrative.milestones.length} /> 里程碑</span>}>
                <Timeline
                  items={narrative.milestones.map((m: any) => ({
                    color: m.type === 'first_success' ? 'green' : 'blue',
                    children: (
                      <div className="text-xs">
                        <span className="mr-1">{m.icon}</span>
                        <span className="font-medium">{m.title}</span>
                        <span className="text-gray-500 ml-2">{m.description}</span>
                      </div>
                    ),
                  }))}
                />
              </Card>
            )}

            {/* 成长轨迹 */}
            {narrative.growth?.trend && (
              <Card className="glass" size="small" title={<span><RiseOutlined /> 成长轨迹</span>}>
                <div className="flex items-center gap-3">
                  <Progress percent={Math.min(Math.max(50 + (narrative.growth.change || 0), 0), 100)}
                    strokeColor={narrative.growth.change >= 0 ? '#52c41a' : '#ff4d4f'} />
                  <div>
                    <div className="text-sm font-medium">{narrative.growth.trend}</div>
                    <div className="text-xs text-gray-500">
                      变化: {(narrative.growth.change || 0) > 0 ? '+' : ''}{narrative.growth.change?.toFixed(1)} 分
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {/* 核心主题 */}
            {narrative.themes?.length > 0 && (
              <Card className="glass" size="small" title="🎯 核心关注">
                <div className="flex gap-2 flex-wrap">
                  {narrative.themes.map((t: any, i: number) => (
                    <Tag key={i} color="purple">{t.theme} ({t.mentions})</Tag>
                  ))}
                </div>
              </Card>
            )}
          </div>
        )}
      </Spin>
    </div>
  )
}
