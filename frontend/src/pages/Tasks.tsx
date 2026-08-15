import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Table, Tag, Button, Modal, Form, Input, Select, DatePicker, Space,
  Popconfirm, Drawer, Descriptions, Tooltip, Segmented, Empty, message, Badge,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined,
  CheckOutlined, InboxOutlined, PauseCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../api'

interface Task {
  id: number
  task_content: string
  task_type: string
  status: string
  priority: string
  deadline: string
  tags: string
  related_doc: string
  create_time: string
  update_time: string
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  todo: { label: '待办', color: 'default' },
  doing: { label: '进行中', color: 'processing' },
  done: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  archived: { label: '归档', color: 'cyan' },
  shelved: { label: '搁置', color: 'warning' },
}
const PRIORITY_COLOR: Record<string, string> = { high: 'red', medium: 'orange', low: 'blue' }
const TYPE_LABELS: Record<string, string> = { work: '💼 工作', life: '🏠 生活', health: '💪 健康', mix: '🔀 混合' }

const STATUS_FLOW: Record<string, string[]> = {
  todo: ['doing', 'done', 'failed', 'shelved'],
  doing: ['done', 'failed', 'todo', 'shelved'],
  done: ['doing', 'archived', 'shelved'],
  failed: ['doing', 'todo', 'shelved'],
  shelved: ['todo', 'doing'],
  archived: [],
}

export default function Tasks() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState({ status: '', task_type: '', priority: '', keyword: '' })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Task | null>(null)
  const [drawerTask, setDrawerTask] = useState<Task | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filter.status) params.set('status', filter.status)
      if (filter.task_type) params.set('task_type', filter.task_type)
      if (filter.priority) params.set('priority', filter.priority)
      if (filter.keyword) params.set('keyword', filter.keyword)
      const qs = params.toString()
      setTasks(await api.getTasks(qs ? `?${qs}` : ''))
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  function openCreate() {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ task_type: 'work', priority: 'medium' })
    setModalOpen(true)
  }

  function openEdit(task: Task) {
    setEditing(task)
    form.setFieldsValue({
      task_content: task.task_content,
      task_type: task.task_type,
      priority: task.priority,
      tags: task.tags,
      deadline: task.deadline ? dayjs(task.deadline) : null,
      related_doc: task.related_doc,
    })
    setModalOpen(true)
  }

  async function handleSubmit() {
    const values = await form.validateFields()
    const data = {
      content: values.task_content,
      task_type: values.task_type,
      priority: values.priority,
      tags: values.tags || '',
      deadline: values.deadline ? values.deadline.format('YYYY-MM-DD') : '',
      related_doc: values.related_doc || '',
    }
    if (editing) {
      await api.updateTask(editing.id, data)
      message.success('更新成功')
    } else {
      await api.createTask(data)
      message.success('创建成功')
    }
    setModalOpen(false)
    load()
  }

  async function handleDelete(id: number) {
    await api.deleteTask(id)
    message.success('已删除')
    load()
  }

  async function handleStatusChange(id: number, status: string) {
    try {
      const task = tasks.find((t) => t.id === id)
      await api.changeTaskStatus(id, status)
      message.success(`状态已更新为「${STATUS_LABELS[status]?.label}」`)
      load()

      // 任务完成时触发演化闭环
      if (status === 'done' && task) {
        triggerEvolution(task)
      }
    } catch (e: any) {
      message.error(e.message || '状态变更失败')
    }
  }

  // 触发演化闭环
  async function triggerEvolution(task: Task) {
    try {
      // 记录行为
      await api.logBehavior('task_complete', {
        task_id: task.id,
        task_type: task.task_type,
        content: task.task_content,
      })

      // 触发演化学习（权重迭代 + 模式学习）
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: `演化学习: ${task.task_content}` }),
      })

      // 静默处理，不影响用户体验
    } catch {
      // 演化失败不影响主流程
    }
  }

  const columns = [
    {
      title: '任务内容',
      dataIndex: 'task_content',
      key: 'content',
      render: (text: string, row: Task) => (
        <a onClick={() => setDrawerTask(row)}>{text}</a>
      ),
    },
    {
      title: '分类',
      dataIndex: 'task_type',
      key: 'type',
      width: 100,
      render: (t: string) => TYPE_LABELS[t] || t,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => {
        const cfg = STATUS_LABELS[s] || { label: s, color: 'default' }
        return <Badge status={cfg.color as any} text={cfg.label} />
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (p: string) => <Tag color={PRIORITY_COLOR[p]}>{p}</Tag>,
    },
    {
      title: '截止时间',
      dataIndex: 'deadline',
      key: 'deadline',
      width: 120,
      render: (d: string) => d || <span className="text-gray-400">—</span>,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 120,
      render: (tags: string) => tags ? tags.split(',').slice(0, 2).map((t) => <Tag key={t}>{t.trim()}</Tag>) : null,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, row: Task) => (
        <Space size="small">
          {STATUS_FLOW[row.status]?.map((ns) => (
            <Tooltip key={ns} title={`标记为「${STATUS_LABELS[ns]?.label}」`}>
              <Button
                size="small"
                type="text"
                icon={statusIcon(ns)}
                onClick={() => handleStatusChange(row.id, ns)}
              />
            </Tooltip>
          ))}
          <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(row)} />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(row.id)}>
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">任务管理</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">全生命周期管理 · 状态流转 · 关联文档</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建任务
        </Button>
      </div>

      {/* 筛选栏 */}
      <Card size="small" className="glass">
        <Space wrap>
          <Segmented
            value={filter.status}
            onChange={(v) => setFilter((f) => ({ ...f, status: v as string }))}
            options={[
              { label: '全部', value: '' },
              { label: '待办', value: 'todo' },
              { label: '进行中', value: 'doing' },
              { label: '已完成', value: 'done' },
              { label: '搁置', value: 'shelved' },
            ]}
          />
          <Select
            placeholder="分类"
            allowClear
            value={filter.task_type || undefined}
            onChange={(v) => setFilter((f) => ({ ...f, task_type: v || '' }))}
            style={{ width: 120 }}
          >
            <Select.Option value="work">💼 工作</Select.Option>
            <Select.Option value="life">🏠 生活</Select.Option>
            <Select.Option value="health">💪 健康</Select.Option>
          </Select>
          <Select
            placeholder="优先级"
            allowClear
            value={filter.priority || undefined}
            onChange={(v) => setFilter((f) => ({ ...f, priority: v || '' }))}
            style={{ width: 100 }}
          >
            <Select.Option value="high">🔴 高</Select.Option>
            <Select.Option value="medium">🟡 中</Select.Option>
            <Select.Option value="low">🔵 低</Select.Option>
          </Select>
          <Input.Search
            placeholder="搜索任务..."
            allowClear
            value={filter.keyword}
            onChange={(e) => setFilter((f) => ({ ...f, keyword: e.target.value }))}
            onSearch={load}
            style={{ width: 200 }}
          />
        </Space>
      </Card>

      {/* 任务表格 */}
      <Card className="glass flex-1">
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 12, showSizeChanger: true }}
          locale={{ emptyText: <Empty description="暂无任务，点击「新建任务」创建" /> }}
          size="middle"
        />
      </Card>

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editing ? '编辑任务' : '新建任务'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        width={560}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="task_content" label="任务内容" rules={[{ required: true, message: '请输入任务内容' }]}>
            <Input.TextArea rows={2} placeholder="描述任务..." />
          </Form.Item>
          <div className="flex gap-3">
            <Form.Item name="task_type" label="分类" className="flex-1">
              <Select>
                <Select.Option value="work">💼 工作</Select.Option>
                <Select.Option value="life">🏠 生活</Select.Option>
                <Select.Option value="health">💪 健康</Select.Option>
                <Select.Option value="mix">🔀 混合</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="priority" label="优先级" className="flex-1">
              <Select>
                <Select.Option value="high">🔴 高</Select.Option>
                <Select.Option value="medium">🟡 中</Select.Option>
                <Select.Option value="low">🔵 低</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="deadline" label="截止时间" className="flex-1">
              <DatePicker className="w-full" format="YYYY-MM-DD" />
            </Form.Item>
          </div>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="例如：周报,文字,紧急" />
          </Form.Item>
          <Form.Item name="related_doc" label="关联文档路径">
            <Input placeholder="例如：D:\docs\计划.docx" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 任务详情抽屉 */}
      <Drawer
        title="任务详情"
        placement="right"
        width={420}
        onClose={() => setDrawerTask(null)}
        open={!!drawerTask}
      >
        {drawerTask && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="内容">{drawerTask.task_content}</Descriptions.Item>
            <Descriptions.Item label="分类">{TYPE_LABELS[drawerTask.task_type]}</Descriptions.Item>
            <Descriptions.Item label="状态">{STATUS_LABELS[drawerTask.status]?.label}</Descriptions.Item>
            <Descriptions.Item label="优先级">
              <Tag color={PRIORITY_COLOR[drawerTask.priority]}>{drawerTask.priority}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="截止时间">{drawerTask.deadline || '—'}</Descriptions.Item>
            <Descriptions.Item label="标签">{drawerTask.tags || '—'}</Descriptions.Item>
            <Descriptions.Item label="关联文档">
              {drawerTask.related_doc ? (
                <a href={`file:///${drawerTask.related_doc}`} target="_blank" rel="noreferrer">
                  📎 {drawerTask.related_doc}
                </a>
              ) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{drawerTask.create_time}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{drawerTask.update_time || '—'}</Descriptions.Item>
            <Descriptions.Item label="知识库检索">
              <a onClick={() => {
                // 跳转到知识库并搜索相关内容
                window.open(`/kb?search=${encodeURIComponent(drawerTask.task_content)}`, '_self')
              }}>
                🔍 搜索相关知识 →
              </a>
            </Descriptions.Item>
            <Descriptions.Item label="DAG 编排">
              <a onClick={() => navigate(`/tasks/${drawerTask.id}/dag`)}>
                📊 查看 DAG →
              </a>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  )
}

function statusIcon(status: string) {
  switch (status) {
    case 'doing': return <PlayCircleOutlined />
    case 'done': return <CheckOutlined />
    case 'archived': return <InboxOutlined />
    case 'shelved': return <PauseCircleOutlined />
    default: return <PlayCircleOutlined />
  }
}
