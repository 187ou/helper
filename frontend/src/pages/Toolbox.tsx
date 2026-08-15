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
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [newDesc, setNewDesc] = useState('')
  const [generating, setGenerating] = useState(false)
  const [running, setRunning] = useState<string | null>(null)
  const [result, setResult] = useState('')
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)

  useEffect(() => {
    loadTools()
  }, [])

  async function loadTools() {
    setLoading(true)
    try {
      const data = await api.getToolList()
      setTools(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('加载工具失败:', e)
      setTools([])
    } finally {
      setLoading(false)
    }
  }

  async function generateTool() {
    if (!newDesc.trim()) return
    setGenerating(true)
    setResult('')
    try {
      const data = await api.generateTool(newDesc)
      if (data.status === 'error') {
        message.error(data.error || '生成失败')
        return
      }

      // 保存到工具库
      await api.saveTool(data.name, data.description, data.code)
      message.success('工具已生成并入库')
      setNewDesc('')
      setModalOpen(false)
      loadTools()
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
      const data = await api.runTool(tool.id)
      setResult(data.output || '执行完成（无输出）')
    } catch (e: any) {
      setResult(`执行失败: ${e.message}`)
    } finally {
      setRunning(null)
    }
  }

  async function deleteTool(tool: Tool) {
    try {
      await api.deleteTool(tool.id)
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
        <Spin spinning={loading}>
          {tools.length === 0 && !loading ? (
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
                    {tool.code?.split('\n').slice(0, 3).join('\n')}...
                  </div>
                  <div className="text-[10px] text-gray-400 mt-2">创建于 {tool.created_at}</div>
                </Card>
              ))}
            </div>
          )}
        </Spin>
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
