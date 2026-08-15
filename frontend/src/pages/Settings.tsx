import { useState, useEffect } from 'react'
import {
  Card, Input, Select, Switch, Button, message, Divider, Tooltip, Row, Col, InputNumber,
  Progress, Modal, Popconfirm, Tag, Empty, Alert,
} from 'antd'
import {
  SaveOutlined, ApiOutlined, ExperimentOutlined, ReloadOutlined,
  DatabaseOutlined, DeleteOutlined, DownloadOutlined, SafetyOutlined,
} from '@ant-design/icons'
import { api } from '../api'

const PRESETS: Record<string, { url: string; model: string }> = {
  LongCat: { url: 'https://api.longcat.chat/openai/v1', model: 'LongCat-2.0' },
  OpenAI: { url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  DeepSeek: { url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  Moonshot: { url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  通义千问: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-turbo' },
  Ollama: { url: 'http://localhost:11434/v1', model: 'llama3.2' },
}

interface EvoConfigs {
  enable_evolution: boolean
  enable_behavior_track: boolean
  enable_auto_optimize: boolean
  enable_template_save: boolean
  enable_tool_gen: boolean
  evolution_threshold: number
}

export default function Settings() {
  const [form, setForm] = useState({ base_url: '', api_key: '', model_name: '' })
  const [showKey, setShowKey] = useState(false)
  const [testResult, setTestResult] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [evoConfigs, setEvoConfigs] = useState<EvoConfigs | null>(null)
  const [evoSchema, setEvoSchema] = useState<Record<string, any>>({})

  // 存储信息
  const [storageInfo, setStorageInfo] = useState<any>(null)
  const [backupLoading, setBackupLoading] = useState(false)

  useEffect(() => {
    api.getSettings().then(setForm)
    api.getEvoConfigs().then((res) => {
      setEvoConfigs(res.configs)
      setEvoSchema(res.schema)
    })
    api.getStorageInfo().then(setStorageInfo)
  }, [])

  function setField(key: string, val: string) {
    setForm((f) => ({ ...f, [key]: val }))
  }

  function applyPreset(name: string) {
    const p = PRESETS[name]
    if (p) setForm((f) => ({ ...f, base_url: p.url, model_name: p.model }))
  }

  async function test() {
    setTestResult({ loading: true })
    const r = await api.testSettings(form)
    setTestResult(r)
  }

  async function save() {
    setSaving(true)
    await api.saveSettings(form)
    setSaving(false)
    message.success('设置已保存')
  }

  async function updateEvoConfig(key: string, value: any) {
    await api.updateEvoConfig(key, value)
    setEvoConfigs((prev => prev ? { ...prev, [key]: value } : prev))
    message.success('已更新')
  }

  async function resetEvoConfigs() {
    const res = await api.resetEvoConfigs()
    setEvoConfigs(res.configs)
    message.success('已恢复默认')
  }

  async function createBackup() {
    setBackupLoading(true)
    try {
      const res = await api.createBackup({})
      message.success(`备份已创建: ${res.path}`)
    } catch (e: any) {
      message.error(e.message || '备份失败')
    } finally {
      setBackupLoading(false)
    }
  }

  async function resetData(target: string, desc: string) {
    Modal.confirm({
      title: '确认重置',
      content: `确定要清空「${desc}」吗？此操作不可恢复。`,
      okText: '确认清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        await api.resetData(target)
        message.success(`已清空: ${desc}`)
      },
    })
  }

  const resetTargets = [
    { key: 'tasks', desc: '任务数据', color: 'blue' },
    { key: 'bills', desc: '记账数据', color: 'green' },
    { key: 'evolution', desc: '演化记忆', color: 'purple' },
    { key: 'behavior', desc: '行为日志', color: 'orange' },
    { key: 'knowledge', desc: '知识库', color: 'cyan' },
    { key: 'habits', desc: '习惯打卡', color: 'magenta' },
    { key: 'notes', desc: '笔记', color: 'geekblue' },
  ]

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">系统设置</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">大模型配置 · 演化控制 · 数据管理 · 隐私安全</p>
      </div>

      <Row gutter={16}>
        <Col span={14}>
          {/* LLM 配置 */}
          <Card
            title={<span><ApiOutlined /> 大模型配置</span>}
            className="glass"
            extra={
              <Tooltip title="支持所有 OpenAI 兼容 API">
                <span className="text-xs text-gray-400">兼容 OpenAI 协议</span>
              </Tooltip>
            }
          >
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">厂商预设</label>
                <Select onChange={applyPreset} placeholder="选择厂商或自定义" className="w-full">
                  {Object.keys(PRESETS).map((name) => (
                    <Select.Option key={name} value={name}>{name}</Select.Option>
                  ))}
                </Select>
              </div>

              <div>
                <label className="text-xs text-gray-500 block mb-1">Base URL</label>
                <Input
                  value={form.base_url}
                  onChange={(e) => setField('base_url', e.target.value)}
                  placeholder="https://api.example.com/v1"
                />
              </div>

              <div>
                <label className="text-xs text-gray-500 block mb-1">API Key</label>
                <Input.Password
                  value={form.api_key}
                  onChange={(e) => setField('api_key', e.target.value)}
                  placeholder="sk-..."
                  visibilityToggle={{ visible: showKey, onVisibleChange: setShowKey }}
                />
              </div>

              <div>
                <label className="text-xs text-gray-500 block mb-1">模型名称</label>
                <Input
                  value={form.model_name}
                  onChange={(e) => setField('model_name', e.target.value)}
                  placeholder="model-name"
                />
              </div>

              <div className="flex gap-3">
                <Button onClick={test}>测试连接</Button>
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
                  保存
                </Button>
              </div>

              {testResult && !testResult.loading && (
                <div className={`p-3 rounded-xl text-sm ${testResult.ok ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-500'}`}>
                  {testResult.ok ? `✅ ${testResult.message}` : `❌ ${testResult.error}`}
                </div>
              )}
            </div>
          </Card>
        </Col>

        <Col span={10}>
          {/* 演化控制 */}
          <Card
            title={<span><ExperimentOutlined /> 演化控制</span>}
            className="glass"
            extra={
              <Tooltip title="恢复默认演化规则">
                <Button size="small" icon={<ReloadOutlined />} onClick={resetEvoConfigs} />
              </Tooltip>
            }
          >
            {evoConfigs ? (
              <div className="space-y-4">
                {Object.entries(evoConfigs).map(([key, value]) => {
                  const schema = evoSchema[key] || {}
                  const label = schema.label || key
                  return (
                    <div key={key} className="flex items-center justify-between">
                      <div className="text-sm">{label}</div>
                      {schema.type === 'bool' ? (
                        <Switch checked={value as boolean} onChange={(v) => updateEvoConfig(key, v)} />
                      ) : schema.type === 'int' ? (
                        <InputNumber
                          min={schema.min} max={schema.max}
                          value={value as number}
                          onChange={(v) => v != null && updateEvoConfig(key, v)}
                          size="small" style={{ width: 100 }}
                        />
                      ) : null}
                    </div>
                  )
                })}

                <Divider className="my-2" />

                <div className="text-xs text-gray-400 space-y-1">
                  <div>关闭「启用自演化」后，系统将停止所有自动优化</div>
                  <div>关闭「行为采集」后，不再记录任何操作行为</div>
                  <div>所有配置仅本地保存，重启生效</div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">加载中...</div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 数据管理 */}
      <Card
        title={<span><DatabaseOutlined /> 数据管理</span>}
        className="glass"
        extra={<span className="text-xs text-gray-400">所有数据本地存储</span>}
      >
        <div className="space-y-4">
          {/* 存储信息 */}
          {storageInfo && (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-gray-50 p-3 rounded-lg">
                <div className="text-xs text-gray-500">总占用</div>
                <div className="text-lg font-semibold">{storageInfo.total_size_formatted}</div>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg">
                <div className="text-xs text-gray-500">数据库</div>
                <div className="text-lg font-semibold">{storageInfo.database.size_formatted}</div>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg">
                <div className="text-xs text-gray-500">数据目录</div>
                <div className="text-xs text-gray-400 truncate">{storageInfo.user_data_root}</div>
              </div>
            </div>
          )}

          {/* 备份 */}
          <div className="flex items-center gap-3">
            <Button icon={<DownloadOutlined />} loading={backupLoading} onClick={createBackup}>
              创建备份
            </Button>
            <span className="text-xs text-gray-400">将所有数据打包为 ZIP 压缩包</span>
          </div>

          <Divider className="my-2" />

          {/* 数据重置 */}
          <div>
            <div className="text-sm font-medium mb-2">数据重置</div>
            <div className="flex flex-wrap gap-2">
              {resetTargets.map((t) => (
                <Button
                  key={t.key}
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => resetData(t.key, t.desc)}
                >
                  {t.desc}
                </Button>
              ))}
            </div>
            <div className="text-xs text-red-400 mt-2">⚠️ 重置操作不可恢复，请谨慎操作</div>
          </div>
        </div>
      </Card>

      {/* 隐私安全 */}
      <Card
        title={<span><SafetyOutlined /> 隐私安全</span>}
        className="glass"
      >
        <Alert
          type="success"
          showIcon
          message="全量数据本地私有化存储"
          description="所有用户数据、记忆、日志、文档、模板全部存储在本地 user_data 目录，无任何云端上传、无日志外传。"
          className="mb-3"
        />
        <div className="text-xs text-gray-500 space-y-1">
          <div>✅ 任务数据、记账记录、演化日志 → 本地 SQLite</div>
          <div>✅ 向量知识库 → 本地 Chroma</div>
          <div>✅ 个人资料、文档 → 本地文件系统</div>
          <div>✅ 沙箱隔离执行 → 无跨目录/网络权限</div>
          <div>✅ 离线模式 → 零网络请求</div>
        </div>
      </Card>
    </div>
  )
}
