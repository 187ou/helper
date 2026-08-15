import { useState, useEffect } from 'react'
import {
  Button, Input, Tree, message, Spin, Empty, Tag, Space, Tooltip,
} from 'antd'
import {
  DesktopOutlined, ReloadOutlined, FolderOutlined, FileOutlined,
  FormatPainterOutlined, ExportOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

interface FileItem {
  name: string
  path: string
  size: number
  suffix: string
}

export default function FileArchiver() {
  const [desktopFiles, setDesktopFiles] = useState<FileItem[]>([])
  const [archiveFiles, setArchiveFiles] = useState<FileItem[]>([])
  const [loading, setLoading] = useState(false)
  const [dirInput, setDirInput] = useState('')

  async function loadDesktop() {
    setLoading(true)
    try {
      const files = await api.scanDesktop()
      setDesktopFiles(files)
    } catch (e: any) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadArchive() {
    setLoading(true)
    try {
      const files = await api.scanArchive()
      setArchiveFiles(files)
    } catch (e: any) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDesktop()
    loadArchive()
  }, [])

  function formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  function renderFiles(files: FileItem[]) {
    if (files.length === 0) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无文件" />
    return (
      <div className="space-y-1">
        {files.map((f) => (
          <div key={f.path} className="flex items-center gap-2 text-sm p-1.5 hover:bg-gray-50 rounded">
            <FileOutlined className="text-gray-400" />
            <span className="flex-1 truncate">{f.name}</span>
            <Tag className="text-xs">{f.suffix || '未知'}</Tag>
            <span className="text-xs text-gray-400">{formatSize(f.size)}</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex gap-4 h-full">
      <div className="w-1/2 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium"><DesktopOutlined /> 桌面文件</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={loadDesktop} loading={loading} />
        </div>
        <div className="flex-1 overflow-y-auto border rounded-lg p-2 bg-gray-50/50">
          <Spin spinning={loading}>{renderFiles(desktopFiles)}</Spin>
        </div>
        <div className="text-xs text-gray-400">
          共 {desktopFiles.length} 个文件 · 建议定期归档整理
        </div>
      </div>

      <div className="w-1/2 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium"><FolderOutlined /> 归档目录</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={loadArchive} loading={loading} />
        </div>
        <div className="flex-1 overflow-y-auto border rounded-lg p-2 bg-gray-50/50">
          <Spin spinning={loading}>{renderFiles(archiveFiles)}</Spin>
        </div>
        <div className="text-xs text-gray-400">
          共 {archiveFiles.length} 个文件
        </div>
      </div>
    </div>
  )
}
