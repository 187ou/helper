import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

const CAT_LABELS = {
  work_doc: '工作文档',
  contract: '合同',
  personal: '个人',
  note: '笔记',
  bill: '账单',
}

export default function Knowledge() {
  const [docs, setDocs] = useState([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const fileRef = useRef(null)

  const load = () => api.getDocs().then(setDocs)
  useEffect(() => { load() }, [])

  async function upload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    form.append('category', 'work_doc')
    await fetch('/api/kb/upload', { method: 'POST', body: form })
    load()
    e.target.value = ''
  }

  async function search() {
    if (!query.trim()) return
    const r = await api.searchDocs(query)
    setResults(r)
  }

  async function del(doc) {
    await api.deleteDoc(doc.file_path, doc.category)
    load()
  }

  return (
    <div className="h-full flex flex-col p-8 gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">知识库</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">本地文档上传 · 归类 · 语义检索</p>
      </div>

      {/* 工具栏 */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => fileRef.current?.click()}
          className="px-4 py-2 bg-[var(--color-accent)] text-white rounded-xl text-sm hover:bg-[var(--color-accent-hi)]"
        >
          + 上传
        </button>
        <button onClick={load} className="px-4 py-2 glass rounded-xl text-sm hover:bg-white/70">
          刷新
        </button>
        <span className="text-xs text-[var(--color-text-muted)] ml-auto">共 {docs.length} 个文档</span>
        <input ref={fileRef} type="file" onChange={upload} className="hidden" accept=".txt,.md,.pdf,.docx,.xlsx" />
      </div>

      {/* 搜索 */}
      <div className="glass rounded-xl flex items-center gap-2 px-4 py-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          placeholder="🔍 语义检索..."
          className="flex-1 bg-transparent border-none outline-none text-sm py-1"
        />
        <button onClick={search} className="text-xs px-3 py-1 glass rounded-lg hover:bg-white/70">
          搜索
        </button>
      </div>

      {/* 搜索结果 */}
      {results && (
        <div className="glass rounded-xl p-4 text-sm space-y-2">
          <div className="text-xs text-[var(--color-text-sec)] mb-2">搜索结果 ({results.length})</div>
          {results.map((r, i) => (
            <div key={i} className="p-2 bg-white/40 rounded-lg">
              <span className="text-[var(--color-accent)]">[{r.file_name}]</span> {r.text?.slice(0, 100)}...
            </div>
          ))}
        </div>
      )}

      {/* 文档列表 */}
      <div className="flex-1 glass rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-[var(--color-text-sec)] border-b border-[var(--color-border)]">
              <th className="text-left p-3 font-medium">文件</th>
              <th className="text-left p-3 font-medium">分类</th>
              <th className="text-right p-3 font-medium">切片</th>
              <th className="text-right p-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {docs.length === 0 && (
              <tr><td colSpan={4} className="text-center text-[var(--color-text-muted)] p-8">暂无文档</td></tr>
            )}
            {docs.map((d, i) => (
              <tr key={i} className="border-b border-[var(--color-border)] hover:bg-white/30">
                <td className="p-3">{d.file_name}</td>
                <td className="p-3 text-[var(--color-text-sec)]">{CAT_LABELS[d.category] || d.category}</td>
                <td className="p-3 text-right text-[var(--color-text-muted)]">{d.total_chunks}</td>
                <td className="p-3 text-right">
                  <button onClick={() => del(d)} className="text-xs text-[var(--color-danger)] hover:underline">
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
