import { useState, useEffect } from 'react'
import {
  Card, Table, Tag, Button, Modal, Input, message, Empty, Tooltip, Popconfirm, Descriptions,
} from 'antd'
import {
  CaretRightOutlined, LockOutlined, UnlockOutlined, DeleteOutlined, EyeOutlined,
} from '@ant-design/icons'

interface Template {
  id: number
  name: string
  steps: any[]
  freq: number
  create_time: string
  is_locked?: boolean
}

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(false)
  const [detailTpl, setDetailTpl] = useState<Template | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      // 模板数据来自后端 evolution_core/template_save.py
      // 临时使用模拟数据展示 UI（后端接口待扩展）
      setTemplates([
        { id: 1, name: '周报生成', steps: [{ name: '收集工作信息' }, { name: '撰写正文' }, { name: '汇总输出' }], freq: 5, create_time: '2026-08-10' },
        { id: 2, name: '报销整理', steps: [{ name: '归集票据' }, { name: '填写明细' }, { name: '格式规范' }], freq: 3, create_time: '2026-08-12' },
      ])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const columns = [
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
            <Button size="small" type="text" icon={<CaretRightOutlined />} onClick={() => message.info('启动模板执行')} />
          </Tooltip>
          <Tooltip title={row.is_locked ? '解锁（允许自动覆盖）' : '锁定（禁止自动覆盖）'}>
            <Button
              size="small"
              type="text"
              icon={row.is_locked ? <LockOutlined /> : <UnlockOutlined />}
              onClick={() => message.success(row.is_locked ? '已解锁' : '已锁定')}
            />
          </Tooltip>
          <Popconfirm title="确认删除模板？" onConfirm={() => message.success('已删除')}>
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </>
      ),
    },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">模板库</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          高频工作流自动固化 · 一键启动全流程 · 锁定后禁止自动覆盖
        </p>
      </div>

      <Card className="glass flex-1">
        <Table
          dataSource={templates}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无固化模板，高频任务将自动生成" /> }}
        />
      </Card>

      <Modal
        title={detailTpl?.name}
        open={!!detailTpl}
        onCancel={() => setDetailTpl(null)}
        footer={null}
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
                    <span>{s.name}</span>
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
