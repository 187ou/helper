import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Card, Button, Spin, Empty, Tag, Descriptions, message, Result } from 'antd'
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons'
import DagGraph, { DagNode } from '../components/DagGraph'
import { api } from '../api'

const STATUS_LABELS: Record<string, string> = {
  pending: '未执行', running: '执行中', success: '成功', failed: '失败',
}

export default function TaskDag() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dagData, setDagData] = useState<{ nodes: DagNode[]; edges: any[] } | null>(null)
  const [selectedNode, setSelectedNode] = useState<DagNode | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getTaskDag(Number(id))
      setDagData(data)
    } catch (e: any) {
      setError(e.message || '加载 DAG 失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (id) load() }, [id])

  const successCount = dagData?.nodes.filter((n) => n.status === 'success').length ?? 0
  const failedCount = dagData?.nodes.filter((n) => n.status === 'failed').length ?? 0
  const totalCount = dagData?.nodes.length ?? 0

  return (
    <div className="h-full flex flex-col p-6 gap-4">
      {/* 头部 */}
      <div className="flex items-center gap-3">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          返回任务
        </Button>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">
          任务 DAG 编排
          <span className="text-sm font-normal text-gray-400 ml-2">#{id}</span>
        </h1>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          刷新
        </Button>
        {totalCount > 0 && (
          <div className="ml-auto text-sm text-gray-500">
            节点 {totalCount} · <span className="text-green-600">成功 {successCount}</span>
            {failedCount > 0 && <span className="text-red-500 ml-2">失败 {failedCount}</span>}
          </div>
        )}
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* DAG 画布 */}
        <Card className="glass flex-1" styles={{ body: { height: '100%', padding: 0 } }}>
          <Spin spinning={loading}>
            {error ? (
              <Result
                status="warning"
                title="暂无 DAG 数据"
                subTitle={error}
                extra={<Button onClick={load}>重试</Button>}
              />
            ) : dagData ? (
              <div style={{ height: '100%', minHeight: 500 }}>
                <DagGraph
                  nodes={dagData.nodes}
                  edges={dagData.edges}
                  onNodeClick={setSelectedNode}
                />
              </div>
            ) : (
              <Empty description="无数据" />
            )}
          </Spin>
        </Card>

        {/* 节点详情 */}
        {selectedNode && (
          <Card title="节点详情" className="w-72 glass" size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="名称">{selectedNode.label}</Descriptions.Item>
              <Descriptions.Item label="描述">{selectedNode.desc || '—'}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={selectedNode.status === 'success' ? 'green' : selectedNode.status === 'failed' ? 'red' : 'blue'}>
                  {STATUS_LABELS[selectedNode.status]}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="类型">{selectedNode.step_type || 'action'}</Descriptions.Item>
            </Descriptions>
            {selectedNode.status === 'failed' && (
              <Button
                block
                size="small"
                type="primary"
                danger
                className="mt-3"
                onClick={() => message.info('重试功能需配合后端 LangGraph 断点续跑')}
              >
                🔄 重试该节点
              </Button>
            )}
          </Card>
        )}
      </div>

      {/* 图例 */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span>图例：</span>
        <span><span className="inline-block w-3 h-3 rounded bg-gray-200 border border-gray-400 mr-1" />未执行</span>
        <span><span className="inline-block w-3 h-3 rounded bg-blue-100 border border-blue-500 mr-1" />执行中</span>
        <span><span className="inline-block w-3 h-3 rounded bg-green-100 border border-green-500 mr-1" />成功</span>
        <span><span className="inline-block w-3 h-3 rounded bg-red-100 border border-red-500 mr-1" />失败</span>
      </div>
    </div>
  )
}
