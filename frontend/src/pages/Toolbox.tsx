import { useState, useEffect } from 'react'
import {
  Card, Button, Input, Modal, message, Empty, Tag, Tooltip, Popconfirm, Spin,
} from 'antd'
import {
  CaretRightOutlined, DeleteOutlined, PlusOutlined, RobotOutlined, CodeOutlined,
} from '@ant-design/icons'
import { api } from '../api'

interface Tool {
  id: string
  name: string
  description: string
  code: string
  status: 'active' | 'generated'
  created_at: string
}

export default function Toolbox() {
  const [tools, setTools] = useState<Tool[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [newDesc, setNewDesc] = useState('')
  const [generating, setGenerating] = useState(false)
  const [running, setRunning] = useState<string | null>(null)
  const [result, setResult] = useState('')
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)

  // 加载工具列表
  useEffect(() => {
    loadTools()
  }, [])

  async function loadTools() {
    try {
      const res = await fetch('/api/tool/list')
      const data = await res.json()
      setTools(data)
    } catch {
      // 后端不可用时保持空列表
    }
  }

  async function generateTool() {
    if (!newDesc.trim()) return
    setGenerating(true)
    setResult('')
    try {
      const res = await fetch('/api/tool/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: newDesc }),
      })
      const data = await res.json()
      if (data.status === 'error') {
        message.error(data.error || '生成失败')
        return
      }

      // 保存到工具库
      const saveRes = await fetch(`/api/tool/${data.name}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: data.name,
          description: data.description,
          code: data.code,
        }),
      })
      if (saveRes.ok) {
        message.success('工具已生成并入库')
        setNewDesc('')
        setModalOpen(false)
        loadTools()
      } else {
        message.warning('生成成功但保存失败')
      }
    } catch (e: any) {
      message.error(e.message || '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  async function runTool(tool: Tool) {
    setRunning(tool.id)
    setResult('')
    setSelectedTool(tool)
    try {
      const res = await fetch(`/api/tool/${tool.id}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      setResult(data.output || '执行完成（无输出）')
    } catch (e: any) {
      setResult(`执行失败: ${e.message}`)
    } finally {
      setRunning(null)
    }
  }

  async function deleteTool(tool: Tool) {
    try {
      await fetch(`/api/tool/${tool.id}`, { method: 'DELETE' })
      message.success('已删除')
      loadTools()
    } catch {
      message.error('删除失败')
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
          <Empty description="暂无工具，点击「生成新工具」创建或等待系统自动生成" />
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
                    <Popconfirm title="确认删除？" onConfirm={() => deleteTool(tool)}>
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

      {/* 运行结果 */}
      {result && (
        <Card
          size="small"
          title={<span>🛠️ 运行结果: {selectedTool?.name}</span>}
          extra={<Button size="small" onClick={() => setResult('')}>关闭</Button>}
          className="glass"
        >
          <pre className="whitespace-pre-wrap text-xs bg-gray-900 text-green-400 p-3 rounded font-mono max-h-48 overflow-y-auto">
            {result}
          </pre>
        </Card>
      )}

      <Modal
        title="生成新工具"
        open={modalOpen}
        onOk={generateTool}
        onCancel={() => { setModalOpen(false); setNewDesc('') }}
        okText="生成"
        confirmLoading={generating}
      >
        <Spin spinning={generating} tip="AI 生成中...">
          <Input.TextArea
            rows={3}
            placeholder="描述你需要的功能，例如：批量重命名文件、统计月度消费、计算税费..."
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
          />
        </Spin>
        <p className="text-xs text-gray-400 mt-2">
          <CodeOutlined /> AI 将生成轻量化脚本，沙箱安全测试后入库
        </p>
      </Modal>
    </div>
  )
}
