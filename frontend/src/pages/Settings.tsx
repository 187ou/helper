import { useState, useEffect } from 'react'
import {
  Card, Input, Select, Switch, Button, message, Divider, Tooltip, Row, Col, InputNumber,
} from 'antd'
import {
  SaveOutlined, ApiOutlined, ExperimentOutlined, ReloadOutlined,
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

  useEffect(() => {
    api.getSettings().then(setForm)
    api.getEvoConfigs().then((res) => {
      setEvoConfigs(res.configs)
      setEvoSchema(res.schema)
    })
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

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">系统设置</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">大模型配置 · 演化控制 · 隐私安全</p>
      </div>

      <Row gutter={16} className="flex-1">
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
                      <div>
                        <div className="text-sm">{label}</div>
                      </div>
                      {schema.type === 'bool' ? (
                        <Switch
                          checked={value as boolean}
                          onChange={(v) => updateEvoConfig(key, v)}
                        />
                      ) : schema.type === 'int' ? (
                        <InputNumber
                          min={schema.min}
                          max={schema.max}
                          value={value as number}
                          onChange={(v) => v != null && updateEvoConfig(key, v)}
                          size="small"
                          style={{ width: 100 }}
                        />
                      ) : null}
                    </div>
                  )
                })}

                <Divider className="my-2" />

                <div className="text-xs text-gray-400 space-y-1">
                  <div>💡 关闭「启用自演化」后，系统将停止所有自动优化</div>
                  <div>🔒 关闭「行为采集」后，不再记录任何操作行为</div>
                  <div>⚠️ 所有配置仅本地保存，重启生效</div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">加载中...</div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
