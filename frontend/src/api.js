const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  // 对话
  checkConfigured: () => request('/chat/configured'),
  sendMessage: (text) => request('/chat/send', {
    method: 'POST',
    body: JSON.stringify({ text }),
  }),

  // 看板
  getToday: () => request('/schedule/today'),
  getWeek: () => request('/schedule/week'),
  addSchedule: (data) => request('/schedule/add', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  completeSchedule: (id) => request('/schedule/complete', {
    method: 'POST',
    body: JSON.stringify({ id }),
  }),
  deleteSchedule: (id) => request(`/schedule/${id}`, { method: 'DELETE' }),

  // 进化
  getStats: () => request('/evolution/stats'),
  getLogs: (type = '') => request(`/evolution/logs?evo_type=${type}`),
  getWeights: () => request('/evolution/weights'),

  // 知识库
  getDocs: () => request('/kb/list'),
  searchDocs: (q) => request(`/kb/search?q=${encodeURIComponent(q)}`),
  deleteDoc: (id, cat) => request(`/kb/${encodeURIComponent(id)}?category=${cat}`, { method: 'DELETE' }),

  // 设置
  getSettings: () => request('/settings/'),
  saveSettings: (data) => request('/settings/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  testSettings: (data) => request('/settings/test', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
}
