import { useState, useEffect } from 'react'
import {
  Card, Button, Input, Select, Space, Empty, Spin, message, Popconfirm, Tag, Modal, List,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, SaveOutlined, EditOutlined, FileOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

const { TextArea } = Input

export default function NoteEditor() {
  const [notes, setNotes] = useState<any[]>([])
  const [editing, setEditing] = useState<any>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('note')
  const [tags, setTags] = useState('')
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      setNotes(await api.getNotes('', keyword))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [keyword])

  function newNote() {
    setEditing(null)
    setTitle('')
    setContent('')
    setCategory('note')
    setTags('')
  }

  function editNote(note: any) {
    setEditing(note)
    setTitle(note.title)
    setContent(note.content)
    setCategory(note.category)
    setTags(note.tags)
  }

  async function save() {
    if (!title.trim()) {
      message.warning('请输入标题')
      return
    }
    const data = { title, content, category, tags }
    if (editing) {
      await api.updateNote(editing.id, data)
      message.success('已更新')
    } else {
      await api.createNote(data)
      message.success('已创建')
    }
    newNote()
    load()
  }

  async function deleteNote(id: number) {
    await api.deleteNote(id)
    message.success('已删除')
    if (editing?.id === id) newNote()
    load()
  }

  return (
    <div className="flex gap-4 h-full">
      {/* 笔记列表 */}
      <div className="w-1/3 flex flex-col gap-3">
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={newNote}>新建</Button>
          <Input.Search placeholder="搜索笔记..." allowClear value={keyword}
            onChange={(e) => setKeyword(e.target.value)} onSearch={load} style={{ width: 180 }} />
        </Space>

        <Spin spinning={loading}>
          <div className="flex-1 overflow-y-auto space-y-2">
            {notes.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无笔记" />}
            {notes.map((n) => (
              <Card
                key={n.id}
                size="small"
                className={`cursor-pointer transition-shadow ${editing?.id === n.id ? 'ring-2 ring-indigo-400' : 'hover:shadow-md'}`}
                onClick={() => editNote(n)}
                title={<span className="text-sm">{n.title}</span>}
                extra={
                  <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); deleteNote(n.id) }}>
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()} />
                  </Popconfirm>
                }
              >
                <div className="text-xs text-gray-500 line-clamp-2">{n.content?.slice(0, 80) || '无内容'}</div>
                <div className="flex items-center gap-2 mt-1">
                  {n.tags && n.tags.split(',').slice(0, 2).map((t: string) => (
                    <Tag key={t} className="text-xs">{t.trim()}</Tag>
                  ))}
                  <span className="text-[10px] text-gray-400 ml-auto">v{n.version}</span>
                </div>
              </Card>
            ))}
          </div>
        </Spin>
      </div>

      {/* 编辑区 */}
      <div className="w-2/3 flex flex-col gap-3">
        <Space>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="笔记标题" className="flex-1" />
          <Select value={category} onChange={setCategory} style={{ width: 100 }}>
            <Select.Option value="note">笔记</Select.Option>
            <Select.Option value="work_doc">工作</Select.Option>
            <Select.Option value="personal">个人</Select.Option>
            <Select.Option value="summary">摘要</Select.Option>
          </Select>
        </Space>

        <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="标签（逗号分隔）" />

        <TextArea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="支持 Markdown 语法..."
          className="flex-1 font-mono text-sm"
          style={{ minHeight: 300 }}
        />

        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">
            {editing ? `版本 ${editing.version} · 创建于 ${editing.create_time?.slice(0, 10)}` : '新笔记'}
          </span>
          <Button type="primary" icon={<SaveOutlined />} onClick={save}>
            {editing ? '更新' : '创建'}
          </Button>
        </div>

        {/* 预览 */}
        {content && (
          <Card size="small" title="预览" className="max-h-48 overflow-y-auto">
            <pre className="whitespace-pre-wrap text-sm font-sans">{content}</pre>
          </Card>
        )}
      </div>
    </div>
  )
}
