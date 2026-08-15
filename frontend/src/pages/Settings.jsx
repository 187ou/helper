import { useState, useEffect } from 'react'
import { api } from '../api'

const PRESETS = {
  LongCat: { url: 'https://api.longcat.chat/openai/v1', model: 'LongCat-2.0' },
  OpenAI: { url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  DeepSeek: { url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  Moonshot: { url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  通义千问: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-turbo' },
  Ollama: { url: 'http://localhost:11434/v1', model: 'llama3.2' },
}

export default function Settings() {
  const [form, setForm] = useState({ base_url: '', api_key: '', model_name: '' })
  const [showKey, setShowKey] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getSettings().then(setForm)
  }, [])

  function setField(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
  }

  function applyPreset(name) {
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
    setTestResult({ ok: true, message: '已保存' })
  }

  return (
    <div className="h-full flex flex-col p-8 gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">设置</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">大模型配置 · 连接测试</p>
      </div>

      <div className="flex-1 glass rounded-2xl p-6 max-w-lg">
        <div className="space-y-4">
          {/* 厂商预设 */}
          <div>
            <label className="text-xs text-[var(--color-text-sec)] block mb-1.5">厂商</label>
            <select
              onChange={(e) => applyPreset(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-white/70 border border-[var(--color-border-mid)] outline-none text-sm"
            >
              <option value="">自定义</option>
              {Object.keys(PRESETS).map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>

          {/* Base URL */}
          <div>
            <label className="text-xs text-[var(--color-text-sec)] block mb-1.5">Base URL</label>
            <input
              value={form.base_url}
              onChange={(e) => setField('base_url', e.target.value)}
              placeholder="https://api.example.com/v1"
              className="w-full px-4 py-2.5 rounded-xl bg-white/70 border border-[var(--color-border-mid)] outline-none text-sm"
            />
          </div>

          {/* API Key */}
          <div>
            <label className="text-xs text-[var(--color-text-sec)] block mb-1.5">API Key</label>
            <input
              type={showKey ? 'text' : 'password'}
              value={form.api_key}
              onChange={(e) => setField('api_key', e.target.value)}
              placeholder="sk-..."
              className="w-full px-4 py-2.5 rounded-xl bg-white/70 border border-[var(--color-border-mid)] outline-none text-sm"
            />
            <label className="flex items-center gap-2 mt-2 text-xs text-[var(--color-text-sec)]">
              <input type="checkbox" checked={showKey} onChange={(e) => setShowKey(e.target.checked)} className="rounded" />
              显示 Key
            </label>
          </div>

          {/* 模型 */}
          <div>
            <label className="text-xs text-[var(--color-text-sec)] block mb-1.5">模型</label>
            <input
              value={form.model_name}
              onChange={(e) => setField('model_name', e.target.value)}
              placeholder="model-name"
              className="w-full px-4 py-2.5 rounded-xl bg-white/70 border border-[var(--color-border-mid)] outline-none text-sm"
            />
          </div>

          {/* 按钮 */}
          <div className="flex gap-3 pt-2">
            <button onClick={test} className="px-5 py-2.5 glass rounded-xl text-sm hover:bg-white/70">
              测试
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="px-5 py-2.5 bg-[var(--color-accent)] text-white rounded-xl text-sm hover:bg-[var(--color-accent-hi)] disabled:opacity-50"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>

          {/* 测试结果 */}
          {testResult && (
            <div
              className={`p-3 rounded-xl text-sm ${
                testResult.loading
                  ? 'bg-white/50 text-[var(--color-text-muted)]'
                  : testResult.ok
                    ? 'bg-green-50 text-[var(--color-success)]'
                    : 'bg-red-50 text-[var(--color-danger)]'
              }`}
            >
              {testResult.loading ? '测试中...' : testResult.ok ? `✅ ${testResult.message}` : `❌ ${testResult.error}`}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
