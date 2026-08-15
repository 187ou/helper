import { useState } from 'react'
import { Tabs, Card } from 'antd'
import {
  FileTextOutlined, TableOutlined, WalletOutlined,
  FolderOutlined, ProjectOutlined,
} from '@ant-design/icons'
import DocWriter from '../components/work/DocWriter'
import ExcelProcessor from '../components/work/ExcelProcessor'
import Reimbursement from '../components/work/Reimbursement'
import FileArchiver from '../components/work/FileArchiver'
import ProjectManager from '../components/work/ProjectManager'

export default function Work() {
  const [activeTab, setActiveTab] = useState('doc')

  const items = [
    {
      key: 'doc',
      label: <span><FileTextOutlined /> 文书撰写</span>,
      children: <DocWriter />,
    },
    {
      key: 'excel',
      label: <span><TableOutlined /> Excel 处理</span>,
      children: <ExcelProcessor />,
    },
    {
      key: 'reimbursement',
      label: <span><WalletOutlined /> 报销整理</span>,
      children: <Reimbursement />,
    },
    {
      key: 'archive',
      label: <span><FolderOutlined /> 文件归档</span>,
      children: <FileArchiver />,
    },
    {
      key: 'project',
      label: <span><ProjectOutlined /> 项目管控</span>,
      children: <ProjectManager />,
    },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">职场办公</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          文书撰写 · Excel 处理 · 报销整理 · 文件归档 · 项目管控
        </p>
      </div>

      <Card className="glass flex-1">
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
      </Card>
    </div>
  )
}
