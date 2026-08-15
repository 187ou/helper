import { useState } from 'react'
import { FloatButton, Input, Select, message } from 'antd'
import { PlusOutlined, SendOutlined } from '@ant-design/icons'
import { api } from '../api'

export default function QuickInput() {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [type, setType] = useState('task')

  async function submit() {
    if (!text.trim()) return
    try {
      if (type === 'task') {
        await api.createTask({ content: text.trim(), task_type: 'work' })
        message.success('任务已创建')
      } else {
        // 快速发送 AI 指令
        await api.sendMessage(text.trim())
        message.success('指令已发送')
      }
      setText('')
      setOpen(false)
    } catch (e: any) {
      message.error(e.message || '操作失败')
    }
  }

  return (
    <>
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-80 p-4 bg-white rounded-2xl shadow-2xl border border-gray-100 space-y-3">
          <Select value={type} onChange={setType} className="w-full" size="small">
            <Select.Option value="task">✅ 快速创建任务</Select.Option>
            <Select.Option value="ai">💬 发送 AI 指令</Select.Option>
          </Select>
          <Input.TextArea
            autoFocus
            rows={2}
            placeholder={type === 'task' ? '任务内容...' : '输入指令...'}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
          />
          <div className="flex justify-end gap-2">
            <button
              className="px-3 py-1 text-xs text-gray-500 hover:bg-gray-100 rounded-lg"
              onClick={() => setOpen(false)}
            >
              取消
            </button>
            <button
              className="px-3 py-1 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 flex items-center gap-1"
              onClick={submit}
            >
              <SendOutlined /> 发送
            </button>
          </div>
        </div>
      )}
      <FloatButton
        icon={<PlusOutlined />}
        tooltip="快速创建"
        onClick={() => setOpen(!open)}
        className="bottom-6 right-6"
      />
    </>
  )
}
