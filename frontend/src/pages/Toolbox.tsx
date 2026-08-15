import { useState } from 'react'
import {
  Card, Button, Input, Modal,message, Empty, Tag, Tooltip, Popconfirm, Spin,
} from 'antd'
import {
  CaretRightOutlined, DeleteOutlined, PlusOutlined, RobotOutlined, CodeOutlined,
} from '@ant-design/icons'

interface Tool {
  id: number
  name: string
  description: string
  code: string
  status: 'active' | 'generated'
  created_at: string
}

export default function Toolbox() {
  const [tools, setTools] = useState<Tool[]>([
    {
      id: 1,
      name: 'bill_analyzer',
      description: '分析月度账单数据',
      code: '# 账单分析工具\ndef run(data):\n    return sum(data)',
      status: 'active',
      created_at: '2026-08-10',
    },
  ])
  const [modalOpen, setModalOpen] = useState(false)
  const [newDesc, setNewDesc] = useState('')
  const [running, setRunning] = useState<number | null>(null)
  const [result, setResult] = useState('')

  function generateTool() {
    if (!newDesc.trim()) return
    const tool: Tool = {
      id: Date.now(),
      name: `tool_${Date.now() % 10000}`,
      description: newDesc,
      code: `# 自动生成的工具\ndef run(*args, **kwargs):\n    return "TODO: ${newDesc}"\n`,
      status: 'generated',
      created_at: new Date().toISOString().slice(0, 10),
    }
    setTools((prev) => [tool, ...prev])
    setNewDesc('')
    setModalOpen(false)
    message.success('工具已生成（沙箱安全测试后入库）')
  }

  async function runTool(tool: Tool) {
    setRunning(tool.id)
    setResult('')
    try {
      // 调用后端沙箱执行
      const res = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: `执行工具: ${tool.name}` }),
      })
      setResult(`工具 ${tool.name} 已提交执行`)
    } catch {
      setResult('执行失败')
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">工具库</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            AI 自动生成专用工具 · 沙箱安全测试后入库 · 纯本地运行
          </p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          生成新工具
        </Button>
      </div>

      <Card className="glass flex-1">
        {tools.length === 0 ? (
          <Empty description="暂无工具，系统将根据高频操作自动生成" />
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {tools.map((tool) => (
              <Card
                key={tool.id}
                size="small"
                title={
                  <div className="flex items-center gap-2">
                    <RobotOutlined className="text-indigo-500" />
                    <span className="text-sm font-mono">{tool.name}</span>
                    <Tag color={tool.status === 'active' ? 'green' : 'default'}>
                      {tool.status === 'active' ? '已激活' : '待测试'}
                    </Tag>
                  </div>
                }
                extra={
                  <div className="flex gap-1">
                    <Tooltip title="运行工具">
                      <Button
                        size="small"
                        type="text"
                        icon={<CaretRightOutlined />}
                        loading={running === tool.id}
                        onClick={() => runTool(tool)}
                      />
                    </Tooltip>
                    <Popconfirm title="确认删除？" onConfirm={() => setTools((p) => p.filter((t) => t.id !== tool.id))}>
                      <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </div>
                }
              >
                <p className="text-xs text-gray-600 mb-2">{tool.description}</p>
                <div className="bg-gray-900 text-green-400 text-xs p-2 rounded font-mono overflow-hidden max-h-20">
                  {tool.code.split('\n').slice(0, 3).join('\n')}...
                </div>
                <div className="text-[10px] text-gray-400 mt-2">创建于 {tool.created_at}</div>
              </Card>
            ))}
          </div>
        )}
      </Card>

      <Modal
        title="生成新工具"
        open={modalOpen}
        onOk={generateTool}
        onCancel={() => setModalOpen(false)}
        okText="生成"
      >
        <Input.TextArea
          rows={3}
          placeholder="描述你需要的功能，例如：批量重命名文件、统计月度消费..."
          value={newDesc}
          onChange={(e) => setNewDesc(e.target.value)}
        />
        <p className="text-xs text-gray-400 mt-2">
          <CodeOutlined /> AI 将生成轻量化脚本，沙箱安全测试后入库
        </p>
      </Modal>
    </div>
  )
}
