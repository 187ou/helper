import { useState } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import TaskDag from './pages/TaskDag'
import Evolution from './pages/Evolution'
import Knowledge from './pages/Knowledge'
import Settings from './pages/Settings'
import ScheduleConfig from './pages/ScheduleConfig'
import Templates from './pages/Templates'
import Toolbox from './pages/Toolbox'
import Work from './pages/Work'
import Life from './pages/Life'
import TextTools from './pages/TextTools'
import GlobalSearch from './components/GlobalSearch'
import QuickInput from './components/QuickInput'

function App() {
  const [page, setPage] = useState('dashboard')

  return (
    <HashRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar current={page} onChange={setPage} />
        <main className="flex-1 overflow-hidden relative">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/:id/dag" element={<TaskDag />} />
            <Route path="/evolution" element={<Evolution />} />
            <Route path="/kb" element={<Knowledge />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/schedule-settings" element={<ScheduleConfig />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/toolbox" element={<Toolbox />} />
            <Route path="/work" element={<Work />} />
            <Route path="/life" element={<Life />} />
            <Route path="/text-tools" element={<TextTools />} />
          </Routes>
          <GlobalSearch />
          <QuickInput />
        </main>
      </div>
    </HashRouter>
  )
}

export default App
