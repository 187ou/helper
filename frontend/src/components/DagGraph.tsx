import { useMemo, useCallback } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Position,
  MarkerType,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'

export interface DagNode {
  id: string
  label: string
  desc?: string
  status: 'pending' | 'running' | 'success' | 'failed'
  step_type?: string
}
export interface DagEdge {
  source: string
  target: string
}

const STATUS_COLOR: Record<string, { bg: string; border: string; text: string }> = {
  pending: { bg: '#f5f5f5', border: '#d9d9d9', text: '#8c8c8c' },
  running: { bg: '#e6f7ff', border: '#1890ff', text: '#1890ff' },
  success: { bg: '#f6ffed', border: '#52c41a', text: '#52c41a' },
  failed: { bg: '#fff2f0', border: '#ff4d4f', text: '#ff4d4f' },
}

function DagNodeComponent({ data }: { data: any }) {
  const status = data.status || 'pending'
  const colors = STATUS_COLOR[status] || STATUS_COLOR.pending
  return (
    <div
      className="px-4 py-3 rounded-xl shadow-sm border-2 min-w-[120px] text-center"
      style={{ background: colors.bg, borderColor: colors.border }}
    >
      <div className="text-sm font-medium" style={{ color: colors.text }}>
        {data.label}
      </div>
      {data.desc && (
        <div className="text-xs text-gray-500 mt-1 line-clamp-2">{data.desc}</div>
      )}
      <div className="text-xs mt-1" style={{ color: colors.text }}>
        {status === 'pending' && '⏳ 未执行'}
        {status === 'running' && '🔄 执行中'}
        {status === 'success' && '✅ 成功'}
        {status === 'failed' && '❌ 失败'}
      </div>
    </div>
  )
}

const nodeTypes = { dagNode: DagNodeComponent }

function getLayoutedElements(nodes: Node[], edges: Edge[], direction = 'LR') {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 80 })

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 160, height: 80 })
  })
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target)
  })

  dagre.layout(g)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 80,
        y: nodeWithPosition.y - 40,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

interface Props {
  nodes: DagNode[]
  edges: DagEdge[]
  onNodeClick?: (node: DagNode) => void
}

export default function DagGraph({ nodes: inputNodes, edges: inputEdges, onNodeClick }: Props) {
  const rfNodes: Node[] = useMemo(
    () =>
      inputNodes.map((n) => ({
        id: n.id,
        type: 'dagNode',
        position: { x: 0, y: 0 },
        data: { label: n.label, desc: n.desc, status: n.status },
      })),
    [inputNodes],
  )

  const rfEdges: Edge[] = useMemo(
    () =>
      inputEdges.map((e, i) => ({
        id: `e${i}`,
        source: e.source,
        target: e.target,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#6366f1', strokeWidth: 2 },
      })),
    [inputEdges],
  )

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(rfNodes, rfEdges),
    [rfNodes, rfEdges],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges)

  // 同步布局变化
  useMemo(() => {
    setNodes(layoutedNodes)
    setEdges(layoutedEdges)
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges])

  const handleNodeClick = useCallback(
    (_: any, node: Node) => {
      const orig = inputNodes.find((n) => n.id === node.id)
      if (orig && onNodeClick) onNodeClick(orig)
    },
    [inputNodes, onNodeClick],
  )

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      nodeTypes={{ dagNode: DagNodeComponent }}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={20} color="#e5e7eb" />
      <Controls />
      <MiniMap
        nodeColor={(n) => {
          const s = (n.data?.status as string) || 'pending'
          return STATUS_COLOR[s]?.border || '#d9d9d9'
        }}
        maskColor="rgba(255,255,255,0.8)"
      />
    </ReactFlow>
  )
}
