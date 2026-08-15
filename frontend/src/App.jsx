import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Evolution from './pages/Evolution'
import Knowledge from './pages/Knowledge'
import Settings from './pages/Settings'

const PAGES = {
  chat: Chat,
  dashboard: Dashboard,
  evolution: Evolution,
  kb: Knowledge,
  settings: Settings,
}

function App() {
  const [page, setPage] = useState('chat')
  const Page = PAGES[page]

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar current={page} onChange={setPage} />
      <main className="flex-1 overflow-hidden">
        <Page />
      </main>
    </div>
  )
}

export default App
