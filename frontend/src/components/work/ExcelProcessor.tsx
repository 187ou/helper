import { useState } from 'react'
import {
  Button, Input, Upload, message, Spin, Empty, Descriptions, Tag, Space,
} from 'antd'
import {
  UploadOutlined, BulbOutlined, TableOutlined, ScissorOutlined,
} from '@ant-design/icons'
import { api } from '../../api'

export default function ExcelProcessor() {
  const [filePath, setFilePath] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  async function analyze() {
    if (!filePath) {
      message.warning('请输入 Excel 文件路径')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await api.analyzeExcel({ path: filePath })
      setResult({ type: 'analyze', data: res })
    } catch (e: any) {
      message.error(e.message || '分析失败')
    } finally {
      setLoading(false)
    }
  }

  async function getChart() {
    if (!filePath) {
      message.warning('请输入 Excel 文件路径')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await api.excelChart({ path: filePath })
      setResult({ type: 'chart', data: res })
    } catch (e: any) {
      message.error(e.message || '生成失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex gap-4 h-full">
      <div className="w-2/5 flex flex-col gap-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Excel 文件路径</label>
          <Input value={filePath} onChange={(e) => setFilePath(e.target.value)}
            placeholder="例如：D:\data\销售数据.xlsx" />
        </div>

        <div className="flex gap-2 flex-wrap">
          <Button type="primary" icon={<TableOutlined />} onClick={analyze} loading={loading}>
            分析数据
          </Button>
          <Button icon={<BulbOutlined />} onClick={getChart} loading={loading}>
            智能分析
          </Button>
        </div>

        <div className="text-xs text-gray-400 space-y-1">
          <div>💡 支持 .xlsx / .xls / .csv</div>
          <div>📊 分析包含：字段统计、极值、均值</div>
          <div>🤖 智能分析由 LLM 生成数据洞察</div>
        </div>

        {result?.type === 'analyze' && (
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="工作表">{result.data.sheets?.join(', ')}</Descriptions.Item>
            <Descriptions.Item label="行数">{result.data.rows}</Descriptions.Item>
            <Descriptions.Item label="列数">{result.data.columns}</Descriptions.Item>
          </Descriptions>
        )}
      </div>

      <div className="w-3/5">
        <Spin spinning={loading}>
          {!result && (
            <Empty description="输入文件路径后点击分析" className="mt-16" />
          )}

          {result?.type === 'analyze' && result.data.stats && (
            <div className="space-y-3">
              <div className="text-sm font-medium">📊 数值字段统计</div>
              {Object.entries(result.data.stats).map(([col, stat]: [string, any]) => (
                <div key={col} className="bg-gray-50 p-3 rounded-lg">
                  <Tag color="blue" className="mb-2">{col}</Tag>
                  <div className="grid grid-cols-5 gap-2 text-xs">
                    <div>计数: <strong>{stat.count}</strong></div>
                    <div>求和: <strong>{stat.sum}</strong></div>
                    <div>均值: <strong>{stat.avg}</strong></div>
                    <div>最大: <strong>{stat.max}</strong></div>
                    <div>最小: <strong>{stat.min}</strong></div>
                  </div>
                </div>
              ))}

              <div className="text-sm font-medium mt-3">📋 数据预览</div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <tbody>
                    {result.data.preview?.map((row: any[], i: number) => (
                      <tr key={i} className={i === 0 ? 'bg-gray-100 font-medium' : ''}>
                        {row.map((cell: any, j: number) => (
                          <td key={j} className="border border-gray-200 px-2 py-1">{cell ?? ''}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result?.type === 'chart' && (
            <div>
              <div className="text-sm font-medium mb-2">🤖 LLM 数据分析</div>
              <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-lg">{result.data.analysis}</pre>
            </div>
          )}
        </Spin>
      </div>
    </div>
  )
}
