import { useState, useEffect } from 'react'
import {
  Card, Table, Tag, Button, Modal, message, Empty, Tooltip, Popconfirm, Descriptions,
  List, Badge, Segmented,
} from 'antd'
import {
  CaretRightOutlined, DeleteOutlined, EyeOutlined,
  ThunderboltOutlined, BulbOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

interface Template {
  id: number
  name: string
  steps: any[]
  freq: number
  create_time: string
  is_locked?: boolean
}

export default function Templates() {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(false)
  const [detailTpl, setDetailTpl] = useState<Template | null>(null)
  const [defaultTemplates, setDefaultTemplates] = useState<Record<string, any>>({})
  const [view, setView] = useState<'saved' | 'defaults'>('saved')

  const load = async () => {
    setLoading(true)
    try {
      const [tpls, defaults] = await Promise.all([
        api.getTemplates(),
        api.getDefaultTemplates(),
      ])
      setTemplates(tpls || [])
      setDefaultTemplates(defaults || {})
    } catch (e) {
      console.error('加载模板失败:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function deleteTemplate(id: number) {
    message.success('模板已删除')
    load()
  }

  async function launchTemplate(tpl: Template) {
    try {
      await api.createTask({
        content: `执行模板: ${tpl.name}`,
        task_type: 'work',
        priority: 'medium',
        steps: tpl.steps,
        source: 'template',
      })
      message.success('模板已启动，正在跳转到任务...')
      setTimeout(() => navigate('/tasks'), 500)
    } catch {
      message.error('启动失败')
    }
  }

  async function launchDefaultTemplate(name: string, steps: any[]) {
    try {
      await api.createTask({
        content: `执行模板: ${name}`,
        task_type: 'work',
        priority: 'medium',
        steps,
        source: 'template',
      })
      message.success('模板已启动，正在跳转到任务...')
      setTimeout(() => navigate('/tasks'), 500)
    } catch {
      message.error('启动失败')
    }
  }

  const savedColumns = [
    {
      title: '模板名称',
      dataIndex: 'name',
      render: (name: string) => <span className="font-medium">{name}</span>,
    },
    {
      title: '使用频次',
      dataIndex: 'freq',
      width: 100,
      render: (freq: number) => <Tag color="blue">{freq} 次</Tag>,
    },
    {
      title: '步骤数',
      dataIndex: 'steps',
      width: 80,
      render: (steps: any[]) => <span>{steps?.length || 0} 步</span>,
    },
    {
      title: '创建时间',
      dataIndex: 'create_time',
      width: 120,
    },
    {
      title: '操作',
      width: 180,
      render: (_: any, row: Template) => (
        <>
          <Tooltip title="查看步骤">
            <Button size="small" type="text" icon={<EyeOutlined />} onClick={() => setDetailTpl(row)} />
          </Tooltip>
          <Tooltip title="一键启动">
            <Button size="small" type="text" icon={<CaretRightOutlined />} type="link" onClick={() => launchTemplate(row)} />
          </Tooltip>
          <Popconfirm title="确认删除模板？" onConfirm={() => deleteTemplate(row.id)}>
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </>
      ),
    },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">模板库</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            高频工作流自动固化 · 一键启动全流程 · 最佳实践模板
          </p>
        </div>
        <Button icon={<ThunderboltOutlined />} onClick={() => navigate('/chat')}>
          用 AI 创建模板
        </Button>
      </div>

      <Segmented
        value={view}
        onChange={(v) => setView(v as any)}
        options={[
          { label: <span><Badge count={templates.length} /> 已固化模板</span>, value: 'saved' },
          { label: <span><BulbOutlined /> 最佳实践模板</span>, value: 'defaults' },
        ]}
      />

      <Card className="glass flex-1">
        {view === 'saved' ? (
          <Table
            dataSource={templates}
            columns={savedColumns}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="暂无固化模板，高频任务将自动生成" /> }}
          />
        ) : (
          <List
            grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 3, xl: 3, xxl: 3 }}
            dataSource={Object.entries(defaultTemplates)}
            locale={{ emptyText: <Empty description="暂无默认模板" /> }}
            renderItem={([name, tpl]: [string, any]) => (
              <List.Item>
                <Card
                  size="small"
                  title={<span className="text-sm font-medium">{name}</span>}
                  extra={
                    <Tooltip title="一键启动">
                      <Button size="small" type="link" icon={<CaretRightOutlined />} onClick={() => launchDefaultTemplate(name, tpl.steps)} />
                    </Tooltip>
                  }
                  className="glass"
                >
                  <p className="text-xs text-gray-500 mb-2">{tpl.keywords?.slice(0, 3).join(', ')}</p>
                  <div className="space-y-1">
                    {tpl.steps?.slice(0, 3).map((s: any, i: number) => (
                      <div key={i} className="text-xs text-gray-600">
                        {i + 1}. {s.name || s}
                      </div>
                    ))}
                    {(tpl.steps?.length || 0) > 3 && (
                      <div className="text-xs text-gray-400">...还有 {tpl.steps.length - 3} 步</div>
                    )}
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      <Modal
        title={detailTpl?.name}
        open={!!detailTpl}
        onCancel={() => setDetailTpl(null)}
        footer={[
          <Button key="launch" type="primary" icon={<CaretRightOutlined />} onClick={() => { launchTemplate(detailTpl!); setDetailTpl(null) }}>
            一键启动
          </Button>,
        ]}
        width={500}
      >
        {detailTpl && (
          <>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="使用频次">{detailTpl.freq} 次</Descriptions.Item>
              <Descriptions.Item label="创建时间">{detailTpl.create_time}</Descriptions.Item>
            </Descriptions>
            <div className="mt-4">
              <div className="text-sm font-medium mb-2">执行步骤：</div>
              <div className="space-y-2">
                {detailTpl.steps.map((s: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <Tag color="blue">{i + 1}</Tag>
                    <span>{s.name || s}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </Modal>
    </div>
  )
}
