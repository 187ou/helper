const BASE = '/api'

// 默认超时 30 秒（LLM 调用可能需要更长时间）
const DEFAULT_TIMEOUT = 30000

async function request(path, options = {}) {
  const controller = new AbortController()
  const timeout = options.timeout || DEFAULT_TIMEOUT
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const res = await fetch(BASE + path, {
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      ...options,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error(`请求超时（${timeout / 1000}秒）`)
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
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
  getTemplates: () => request('/evolution/templates'),
  recommendTemplate: (text, type = '') => request(`/evolution/templates/recommend?task_text=${encodeURIComponent(text)}&task_type=${type}`),
  getDefaultTemplates: () => request('/evolution/templates/defaults'),
  getPatterns: (minConf = 0) => request(`/evolution/patterns?min_confidence=${minConf}`),
  minePatterns: () => request('/evolution/patterns/mine', { method: 'POST' }),
  getDailyReport: () => request('/evolution/report/daily'),
  getWeeklyReport: () => request('/evolution/report/weekly'),
  getLatestReport: (type = 'daily') => request(`/evolution/report/latest?report_type=${type}`),
  runForgetting: () => request('/evolution/forgetting', { method: 'POST' }),

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

  // 任务管理
  getTaskStats: () => request('/task/stats'),
  getTasks: (params = '') => request(`/task/list${params}`),
  getTask: (id) => request(`/task/${id}`),
  createTask: (data) => request('/task/create', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateTask: (id, data) => request(`/task/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  changeTaskStatus: (id, status) => request(`/task/${id}/status`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  }),
  deleteTask: (id) => request(`/task/${id}`, { method: 'DELETE' }),
  getTaskDag: (id) => request(`/task/${id}/dag`),
  getTaskOptions: () => request('/task/meta/options'),

  // 全局检索
  globalSearch: (q) => request(`/search/?q=${encodeURIComponent(q)}`),

  // 行为采集
  logBehavior: (eventType, data) => request('/behavior/log', {
    method: 'POST',
    body: JSON.stringify({ event_type: eventType, event_data: data }),
  }),
  getBehaviorStats: () => request('/behavior/stats'),

  // 演化配置
  getEvoConfigs: () => request('/evo-config/'),
  updateEvoConfig: (key, value) => request(`/evo-config/${key}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  }),
  resetEvoConfigs: () => request('/evo-config/reset', { method: 'POST' }),

  // 职场办公 - 文书（LLM 生成需要更长时间）
  genWeekly: (data) => request('/work/doc/weekly', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  genMonthly: (data) => request('/work/doc/monthly', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  genMeeting: (data) => request('/work/doc/meeting', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  polishDoc: (data) => request('/work/doc/polish', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  saveDoc: (data) => request('/work/doc/save', { method: 'POST', body: JSON.stringify(data) }),

  // 职场办公 - Excel
  analyzeExcel: (data) => request('/work/excel/analyze', { method: 'POST', body: JSON.stringify(data) }),
  mergeExcel: (data) => request('/work/excel/merge', { method: 'POST', body: JSON.stringify(data) }),
  excelChart: (data) => request('/work/excel/chart', { method: 'POST', body: JSON.stringify(data) }),

  // 职场办公 - 报销
  analyzeReimbursement: (data) => request('/work/reimbursement/analyze', { method: 'POST', body: JSON.stringify(data) }),
  genReimbursementReport: (data) => request('/work/reimbursement/report', { method: 'POST', body: JSON.stringify(data) }),

  // 职场办公 - 归档
  scanDesktop: () => request('/work/archive/desktop'),
  scanArchive: () => request('/work/archive/scan'),
  classifyFiles: (files) => request('/work/archive/classify', { method: 'POST', body: JSON.stringify({ files }) }),
  batchRename: (files, rule) => request('/work/archive/rename', { method: 'POST', body: JSON.stringify({ files, rule }) }),
  moveToArchive: (src, category) => request('/work/archive/move', { method: 'POST', body: JSON.stringify({ src, category }) }),

  // 职场办公 - 项目
  getProjects: () => request('/work/project/list'),
  getProject: (id) => request(`/work/project/${id}`),
  createProject: (data) => request('/work/project/create', { method: 'POST', body: JSON.stringify(data) }),
  updateProject: (id, data) => request(`/work/project/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProject: (id) => request(`/work/project/${id}`, { method: 'DELETE' }),
  toggleMilestone: (id, index) => request(`/work/project/${id}/milestone/toggle`, { method: 'POST', body: JSON.stringify({ index }) }),

  // 生活健康 - 记账
  getBills: (month = '') => request(`/life/bill/list?month=${month}`),
  addBill: (data) => request('/life/bill/add', { method: 'POST', body: JSON.stringify(data) }),
  deleteBill: (id) => request(`/life/bill/${id}`, { method: 'DELETE' }),
  getBillSummary: (month = '') => request(`/life/bill/summary?month=${month}`),
  getBillCategory: (month = '') => request(`/life/bill/category?month=${month}`),
  getBillTrend: (months = 6) => request(`/life/bill/trend?months=${months}`),

  // 生活健康 - 健康
  getHealthReminders: () => request('/life/health/reminders'),
  updateHealthReminders: (data) => request('/life/health/reminders', { method: 'PUT', body: JSON.stringify(data) }),
  getHealthRecords: (type = '') => request(`/life/health/records?record_type=${type}`),
  addHealthRecord: (data) => request('/life/health/record', { method: 'POST', body: JSON.stringify(data) }),
  getHealthStats: () => request('/life/health/stats'),

  // 生活健康 - 资料归档
  getArchives: (category = '', keyword = '') => request(`/life/archive/list?category=${category}&keyword=${keyword}`),
  addArchive: (data) => request('/life/archive/add', { method: 'POST', body: JSON.stringify(data) }),
  deleteArchive: (id) => request(`/life/archive/${id}`, { method: 'DELETE' }),
  getArchiveCategories: () => request('/life/archive/categories'),

  // 生活健康 - 习惯打卡
  getHabits: () => request('/life/habit/list'),
  createHabit: (data) => request('/life/habit/create', { method: 'POST', body: JSON.stringify(data) }),
  checkinHabit: (id, data) => request(`/life/habit/${id}/checkin`, { method: 'POST', body: JSON.stringify(data) }),
  deleteHabit: (id) => request(`/life/habit/${id}`, { method: 'DELETE' }),
  getHabitCalendar: (id, month = '') => request(`/life/habit/${id}/calendar?month=${month}`),

  // 知识库 - 笔记
  getNotes: (category = '', keyword = '') => request(`/note/list?category=${category}&keyword=${keyword}`),
  getNote: (id) => request(`/note/${id}`),
  createNote: (data) => request('/note/create', { method: 'POST', body: JSON.stringify(data) }),
  updateNote: (id, data) => request(`/note/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteNote: (id) => request(`/note/${id}`, { method: 'DELETE' }),

  // 知识库 - 文档摘要（LLM 调用需要更长时间）
  summarizeDoc: (data) => request('/note/summarize', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  summarizeAndSave: (data) => request('/note/summarize/save', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),

  // AI 能力 - 模式
  getAiMode: () => request('/ai/mode'),
  switchAiMode: (mode) => request('/ai/mode', { method: 'POST', body: JSON.stringify({ mode }) }),
  testConnection: (data) => request('/ai/test', { method: 'POST', body: JSON.stringify(data) }),
  testOllama: (data) => request('/ai/test/ollama', { method: 'POST', body: JSON.stringify(data) }),

  // AI 能力 - 文本处理（LLM 调用需要更长时间）
  rewriteText: (data) => request('/ai/text/rewrite', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  summarizeText: (data) => request('/ai/text/summarize', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  expandText: (data) => request('/ai/text/expand', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  formatText: (data) => request('/ai/text/format', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),
  polishText: (data) => request('/ai/text/polish', { method: 'POST', body: JSON.stringify(data), timeout: 60000 }),

  // 系统能力
  getStorageInfo: () => request('/system/storage-info'),
  createBackup: (data) => request('/system/backup', { method: 'POST', body: JSON.stringify(data) }),
  restoreBackup: (data) => request('/system/restore', { method: 'POST', body: JSON.stringify(data) }),
  resetData: (target) => request(`/system/reset/${target}`, { method: 'DELETE' }),

  // 工具库
  getToolList: () => request('/tool/list'),
  generateTool: (desc) => request('/tool/generate', { method: 'POST', body: JSON.stringify({ description: desc }) }),
  saveTool: (name, desc, code) => request(`/tool/${encodeURIComponent(name)}/save`, { method: 'POST', body: JSON.stringify({ name, description: desc, code }) }),
  runTool: (id) => request(`/tool/${encodeURIComponent(id)}/run`, { method: 'POST', body: JSON.stringify({}) }),
  deleteTool: (id) => request(`/tool/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}
