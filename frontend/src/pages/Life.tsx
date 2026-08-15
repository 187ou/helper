import { useState } from 'react'
import { Tabs } from 'antd'
import {
  WalletOutlined, HeartOutlined, FolderOutlined, CheckSquareOutlined,
} from '@ant-design/icons'
import Ledger from '../components/life/Ledger'
import Health from '../components/life/Health'
import Archive from '../components/life/Archive'
import HabitTracker from '../components/life/HabitTracker'

export default function Life() {
  const [activeTab, setActiveTab] = useState('ledger')

  const items = [
    { key: 'ledger', label: <span><WalletOutlined /> 记账复盘</span>, children: <Ledger /> },
    { key: 'health', label: <span><HeartOutlined /> 健康提醒</span>, children: <Health /> },
    { key: 'archive', label: <span><FolderOutlined /> 资料归档</span>, children: <Archive /> },
    { key: 'habit', label: <span><CheckSquareOutlined /> 习惯打卡</span>, children: <HabitTracker /> },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">生活 · 健康 · 事务</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          收支记账 · 健康提醒 · 资料归档 · 习惯打卡
        </p>
      </div>

      <div className="flex-1">
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
      </div>
    </div>
  )
}
