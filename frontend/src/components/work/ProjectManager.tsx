import { useState, useEffect } from 'react'
import {
  Card, Button, Input, Modal, Form, Progress, Tag, Empty, Spin, Space,
  Popconfirm, Checkbox, message,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

interface Project {
  id: number
  name: string
  description: string
  status: string
  progress: number
  milestones: { name: string; done: boolean }[]
  create_time: string
}

export default function ProjectManager() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Project | null>(null)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      setProjects(await api.getProjects())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function openCreate() {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  function openEdit(p: Project) {
    setEditing(p)
    form.setFieldsValue({ name: p.name, description: p.description, milestones: p.milestones.map((m) => m.name).join('\n') })
    setModalOpen(true)
  }

  async function handleSubmit() {
    const values = await form.validateFields()
    const milestones = (values.milestones || '').split('\n').filter(Boolean)
    const data = { name: values.name, description: values.description || '', milestones }

    if (editing) {
      await api.updateProject(editing.id, data)
      message.success('更新成功')
    } else {
      await api.createProject(data)
      message.success('创建成功')
    }
    setModalOpen(false)
    load()
  }

  async function handleDelete(id: number) {
    await api.deleteProject(id)
    message.success('已删除')
    load()
  }

  async function toggleMilestone(pid: number, index: number) {
    await api.toggleMilestone(pid, index)
    load()
  }

  function statusColor(s: string) {
    return s === 'active' ? 'green' : s === 'paused' ? 'orange' : 'default'
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-500">共 {projects.length} 个项目</span>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建项目
        </Button>
      </div>

      <Spin spinning={loading}>
        {projects.length === 0 ? (
          <Empty description="暂无项目，点击「新建项目」创建" />
        ) : (
          <div className="grid grid-cols-2 gap-4 overflow-y-auto">
            {projects.map((p) => (
              <Card
                key={p.id}
                size="small"
                title={<span className="text-sm">{p.name}</span>}
                extra={
                  <Space size="small">
                    <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(p)} />
                    <Popconfirm title="确认删除？" onConfirm={() => handleDelete(p.id)}>
                      <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                }
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Tag color={statusColor(p.status)}>{p.status}</Tag>
                    <span className="text-xs text-gray-400">{p.create_time?.slice(0, 10)}</span>
                  </div>

                  <Progress percent={p.progress} size="small" />

                  <div className="space-y-1">
                    {p.milestones.map((m, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <Checkbox checked={m.done} onChange={() => toggleMilestone(p.id, i)} />
                        <span className={m.done ? 'line-through text-gray-400' : ''}>{m.name}</span>
                      </div>
                    ))}
                    {p.milestones.length === 0 && <span className="text-xs text-gray-400">暂无里程碑</span>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Spin>

      <Modal
        title={editing ? '编辑项目' : '新建项目'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：Q3 产品迭代" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="项目简介..." />
          </Form.Item>
          <Form.Item name="milestones" label="里程碑（每行一个）">
            <Input.TextArea rows={3} placeholder="需求分析&#10;方案设计&#10;开发实现&#10;测试上线" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
