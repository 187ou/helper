import { useState } from 'react'
import { Tabs } from 'antd'
import {
  DatabaseOutlined, FileTextOutlined, RobotOutlined,
} from '@ant-design/icons'
import DocManager from '../components/knowledge/DocManager'
import NoteEditor from '../components/knowledge/NoteEditor'
import DocSummarizer from '../components/knowledge/DocSummarizer'

export default function Knowledge() {
  const [activeTab, setActiveTab] = useState('docs')

  const items = [
    { key: 'docs', label: <span><DatabaseOutlined /> 文档库</span>, children: <DocManager /> },
    { key: 'notes', label: <span><FileTextOutlined /> 笔记</span>, children: <NoteEditor /> },
    { key: 'summarize', label: <span><RobotOutlined /> 智能摘要</span>, children: <DocSummarizer /> },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">知识库</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          本地向量知识库 · 笔记编辑 · 文档智能摘要
        </p>
      </div>

      <div className="flex-1">
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
      </div>
    </div>
  )
}
