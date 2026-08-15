import { useState, useEffect } from 'react'
import {
  Card, Input, Select, Button, Modal, Form, Empty, Tag, Space, Popconfirm, message, Descriptions,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, SearchOutlined, FolderOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

const CATEGORIES = [
  { value: 'id_card', label: '证件' },
  { value: 'bill', label: '账单' },
  { value: 'medical', label: '就医' },
  { value: 'express', label: '快递' },
  { value: 'note', label: '笔记' },
  { value: 'other', label: '其他' },
]

export default function Archive() {
  const [items, setItems] = useState<any[]>([])
  const [categories, setCategories] = useState<Record<string, number>>({})
  const [filter, setFilter] = useState({ category: '', keyword: '' })
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [detail, setDetail] = useState<any>(null)

  const load = async () => {
    const [list, cats] = await Promise.all([
      api.getArchives(filter.category, filter.keyword),
      api.getArchiveCategories(),
    ])
    setItems(list)
    setCategories(cats)
  }

  useEffect(() => { load() }, [filter])

  async function addItem() {
    const values = await form.validateFields()
    await api.addArchive(values)
    message.success('已添加')
    setModalOpen(false)
    form.resetFields()
    load()
  }

  async function deleteItem(id: number) {
    await api.deleteArchive(id)
    message.success('已删除')
    load()
  }

  return (
    <div className="flex flex-col gap-4">
      <Card size="small" className="glass">
        <Space wrap>
          <Select
            placeholder="分类筛选"
            allowClear
            value={filter.category || undefined}
            onChange={(v) => setFilter({ ...filter, category: v || '' })}
            style={{ width: 120 }}
          >
            {CATEGORIES.map((c) => (
              <Select.Option key={c.value} value={c.value}>{c.label}</Select.Option>
            ))}
          </Select>
          <Input.Search
            placeholder="搜索资料..."
            allowClear
            value={filter.keyword}
            onChange={(e) => setFilter({ ...filter, keyword: e.target.value })}
            onSearch={load}
            style={{ width: 200 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            添加资料
          </Button>
        </Space>
        {Object.keys(categories).length > 0 && (
          <div className="flex gap-2 mt-2">
            {Object.entries(categories).map(([cat, count]) => (
              <Tag key={cat} color="blue">{cat}: {count}</Tag>
            ))}
          </div>
        )}
      </Card>

      {items.length === 0 ? (
        <Empty description="暂无资料" />
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {items.map((item) => (
            <Card
              key={item.id}
              size="small"
              title={<span className="text-sm truncate">{item.title}</span>}
              extra={
                <Popconfirm title="确认删除？" onConfirm={() => deleteItem(item.id)}>
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              }
              onClick={() => setDetail(item)}
              className="cursor-pointer hover:shadow-md transition-shadow"
            >
              <div className="text-xs text-gray-500">
                <Tag>{CATEGORIES.find((c) => c.value === item.category)?.label || item.category}</Tag>
                <div className="mt-1 truncate">{item.description || '无描述'}</div>
                <div className="text-gray-400 mt-1">{item.create_time?.slice(0, 10)}</div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal title="添加资料" open={modalOpen} onOk={addItem} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="资料名称" />
          </Form.Item>
          <Form.Item name="category" label="分类" initialValue="other">
            <Select options={CATEGORIES} />
          </Form.Item>
          <Form.Item name="file_path" label="文件路径">
            <Input placeholder="关联文件路径（可选）" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="备注说明" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="逗号分隔" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title={detail?.title} open={!!detail} onCancel={() => setDetail(null)} footer={null} width={500}>
        {detail && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="分类">{detail.category}</Descriptions.Item>
            <Descriptions.Item label="描述">{detail.description || '—'}</Descriptions.Item>
            <Descriptions.Item label="文件">
              {detail.file_path ? <a href={`file:///${detail.file_path}`} target="_blank" rel="noreferrer">{detail.file_path}</a> : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="标签">{detail.tags || '—'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{detail.create_time}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
