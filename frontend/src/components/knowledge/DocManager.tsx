import { useState, useEffect, useRef } from 'react'
import {
  Button, Input, Select, Table, Tag, message, Spin, Empty, Progress, Space, Modal,
} from 'antd'
import {
  UploadOutlined, SearchOutlined, DeleteOutlined, ReloadOutlined, FileOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

const CAT_OPTIONS = [
  { value: 'work_doc', label: '工作文档' },
  { value: 'contract', label: '合同票据' },
  { value: 'personal', label: '个人笔记' },
  { value: 'note', label: '笔记' },
  { value: 'bill', label: '账单' },
]

export default function DocManager() {
  const [docs, setDocs] = useState<any[]>([])
  const [stats, setStats] = useState<any>({})
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [d, s] = await Promise.all([api.getDocs(), api.getStats()])
      setDocs(d)
      setStats(s)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    const form = new FormData()
    form.append('file', file)
    form.append('category', 'work_doc')

    setUploading(true)
    setUploadProgress(30)

    try {
      await fetch('/api/kb/upload', { method: 'POST', body: form })
      setUploadProgress(100)
      message.success('上传成功')
      load()
    } catch (err: any) {
      message.error(err.message || '上传失败')
    } finally {
      setUploading(false)
      setUploadProgress(0)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function search() {
    if (!query.trim()) {
      setResults(null)
      return
    }
    setLoading(true)
    try {
      const r = await api.searchDocs(query)
      setResults(r)
    } finally {
      setLoading(false)
    }
  }

  async function del(doc: any) {
    await api.deleteDoc(doc.file_path, doc.category)
    message.success('已删除')
    load()
  }

  const columns = [
    {
      title: '文件名', dataIndex: 'file_name',
      render: (name: string) => (
        <span><FileOutlined className="mr-2 text-gray-400" />{name}</span>
      ),
    },
    {
      title: '分类', dataIndex: 'category', width: 100,
      render: (c: string) => <Tag color="blue">{CAT_OPTIONS.find((o) => o.value === c)?.label || c}</Tag>,
    },
    { title: '切片数', dataIndex: 'total_chunks', width: 80, align: 'center' as const },
    {
      title: '上传时间', dataIndex: 'upload_time', width: 160,
      render: (t: string) => t?.slice(0, 16),
    },
    {
      title: '操作', width: 80,
      render: (_: any, row: any) => (
        <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => del(row)} />
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* 统计 + 分类分布 */}
      <div className="flex gap-3">
        {CAT_OPTIONS.map((cat) => (
          <div key={cat.value} className="glass rounded-xl px-4 py-2 text-center flex-1">
            <div className="text-lg font-semibold">{stats[cat.value] || 0}</div>
            <div className="text-xs text-gray-400">{cat.label}</div>
          </div>
        ))}
      </div>

      {/* 工具栏 */}
      <Card className="glass">
        <Space wrap>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => fileRef.current?.click()}>
            上传文档
          </Button>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <span className="text-xs text-gray-400">共 {docs.length} 个文档 · 支持 PDF/Word/TXT/MD/Excel</span>
        </Space>
        {uploading && <Progress percent={uploadProgress} size="small" className="mt-2" />}
        <input ref={fileRef} type="file" onChange={upload} className="hidden"
          accept=".txt,.md,.pdf,.docx,.xlsx,.csv" />
      </Card>

      {/* 搜索 */}
      <Card className="glass">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={search}
            placeholder="语义检索... (回车搜索)"
            prefix={<SearchOutlined />}
          />
          <Button type="primary" onClick={search} loading={loading}>搜索</Button>
        </div>
      </Card>

      {/* 搜索结果 */}
      {results && (
        <Card size="small" title={`搜索结果 (${results.length})`} className="glass">
          {results.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无匹配结果" />
          ) : (
            <div className="space-y-2">
              {results.map((r, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg">
                  <Tag color="blue" className="mb-1">{r.file_name}</Tag>
                  <p className="text-sm text-gray-600">{r.text?.slice(0, 200)}...</p>
                  <span className="text-xs text-gray-400">相关度: {(r.score * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 文档列表 */}
      <Card className="glass flex-1">
        <Spin spinning={loading}>
          <Table dataSource={docs} columns={columns} rowKey="file_path" size="small"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="暂无文档，点击「上传文档」添加" /> }} />
        </Spin>
      </Card>
    </div>
  )
}

import { Card } from 'antd'
