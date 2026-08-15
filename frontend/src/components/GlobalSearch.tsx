import { useState, useEffect, useCallback } from 'react'
import { Modal, Input, List, Tag, Empty, Spin, Tabs } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

interface SearchResults {
  tasks: any[]
  schedules: any[]
  bills: any[]
  logs: any[]
}

export default function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [results, setResults] = useState<SearchResults | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  // Ctrl+K 唤醒
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const search = useCallback(async () => {
    if (!keyword.trim()) {
      setResults(null)
      return
    }
    setLoading(true)
    try {
      setResults(await api.globalSearch(keyword))
    } finally {
      setLoading(false)
    }
  }, [keyword])

  useEffect(() => {
    const t = setTimeout(search, 300)
    return () => clearTimeout(t)
  }, [search])

  function close() {
    setOpen(false)
    setKeyword('')
    setResults(null)
  }

  function goTo(path: string) {
    navigate(path)
    close()
  }

  const totalCount = results
    ? results.tasks.length + results.schedules.length + results.bills.length + results.logs.length
    : 0

  return (
    <>
      {/* 触发提示 */}
      <Modal
        open={open}
        onCancel={close}
        footer={null}
        width={640}
        styles={{ body: { padding: 0 } }}
        closeIcon={null}
      >
        <div className="p-4">
          <Input
            autoFocus
            size="large"
            placeholder="搜索任务、日程、记账、演化日志..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            className="rounded-xl"
          />
        </div>

        <Spin spinning={loading}>
          {keyword && totalCount === 0 && !loading && (
            <div className="px-4 pb-4">
              <Empty description="无匹配结果" />
            </div>
          )}

          {results && totalCount > 0 && (
            <Tabs
              size="small"
              defaultActiveKey="tasks"
              className="px-4 pb-4"
              items={[
                {
                  key: 'tasks',
                  label: `任务 (${results.tasks.length})`,
                  children: (
                    <List
                      dataSource={results.tasks}
                      renderItem={(item) => (
                        <List.Item
                          className="cursor-pointer hover:bg-gray-50 px-2"
                          onClick={() => goTo(`/tasks/${item.id}/dag`)}
                        >
                          <span className="flex-1 truncate">{item.task_content}</span>
                          <Tag>{item.status}</Tag>
                        </List.Item>
                      )}
                    />
                  ),
                },
                {
                  key: 'schedules',
                  label: `日程 (${results.schedules.length})`,
                  children: (
                    <List
                      dataSource={results.schedules}
                      renderItem={(item) => (
                        <List.Item className="px-2">
                          <span className="flex-1 truncate">{item.title}</span>
                          <Tag>{item.schedule_date}</Tag>
                        </List.Item>
                      )}
                    />
                  ),
                },
                {
                  key: 'bills',
                  label: `记账 (${results.bills.length})`,
                  children: (
                    <List
                      dataSource={results.bills}
                      renderItem={(item) => (
                        <List.Item className="px-2">
                          <span className="flex-1 truncate">{item.description || item.category}</span>
                          <Tag color={item.bill_type === 'income' ? 'green' : 'orange'}>
                            ¥{item.amount}
                          </Tag>
                        </List.Item>
                      )}
                    />
                  ),
                },
                {
                  key: 'logs',
                  label: `日志 (${results.logs.length})`,
                  children: (
                    <List
                      dataSource={results.logs}
                      renderItem={(item) => (
                        <List.Item className="px-2">
                          <span className="flex-1 truncate">{item.before_content} → {item.after_content}</span>
                          <Tag color="purple">{item.evo_type}</Tag>
                        </List.Item>
                      )}
                    />
                  ),
                },
              ]}
            />
          )}
        </Spin>
      </Modal>
    </>
  )
}
