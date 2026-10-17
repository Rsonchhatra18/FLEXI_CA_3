import { useCallback, useEffect, useState } from 'react'
import { api, errorText } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import ChatTab from './tabs/ChatTab.jsx'
import KnowledgeTab from './tabs/KnowledgeTab.jsx'
import AutomationTab from './tabs/AutomationTab.jsx'
import GraphTab from './tabs/GraphTab.jsx'
import McpTab from './tabs/McpTab.jsx'
import CoursesTab from './tabs/CoursesTab.jsx'

const TABS = [
  { id: 'chat', label: '💬 Agent Chat' },
  { id: 'kb', label: '📚 Knowledge Base' },
  { id: 'automation', label: '⚙️ Automation' },
  { id: 'graph', label: '🕸️ Agent Graph' },
  { id: 'mcp', label: '🔌 MCP' },
  { id: 'courses', label: '🎓 Course Mapping' },
]

// The active tab lives in the URL hash (#kb, #mcp …) so every tab has its own link.
const tabFromHash = () => TABS.find((t) => `#${t.id}` === window.location.hash)?.id ?? 'chat'
const newThreadId = () => Math.random().toString(36).slice(2, 10)

export default function App() {
  const [tab, setTab] = useState(tabFromHash)
  const [status, setStatus] = useState(null)
  const [threadId, setThreadId] = useState(newThreadId)
  const [messages, setMessages] = useState([]) // lifted here so chat survives tab switches

  const refreshStatus = useCallback(() => {
    api.status().then(setStatus).catch((e) => setStatus({ error: errorText(e) }))
  }, [])

  useEffect(refreshStatus, [refreshStatus])

  useEffect(() => {
    const onHash = () => setTab(tabFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const openTab = (id) => {
    window.location.hash = id
    setTab(id)
  }

  const newChat = () => {
    setThreadId(newThreadId())
    setMessages([])
    openTab('chat')
  }

  return (
    <div className="layout">
      <Sidebar status={status} threadId={threadId} onNewChat={newChat} />

      <main className="main">
        <header className="hero">
          <h1>StudyPilot <span className="hero-icon">🧭</span></h1>
          <p className="tagline">
            An agentic RAG study assistant – adaptive routing, corrective &amp; self-RAG, tools,
            automation workflows and an MCP server.
          </p>
        </header>

        {status?.error && <div className="alert error">{status.error}</div>}
        {status && status.has_key === false && (
          <div className="alert warn">
            🔑 No GROQ_API_KEY found. Copy <code>.env.example</code> to <code>.env</code>, add your key and
            restart <code>python server.py</code>. The knowledge base still works without it.
          </div>
        )}

        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id}
              className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => openTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>

        <section className="tab-body">
          {tab === 'chat' && (
            <ChatTab messages={messages} setMessages={setMessages} threadId={threadId} onAnswered={refreshStatus} />
          )}
          {tab === 'kb' && <KnowledgeTab onChange={refreshStatus} />}
          {tab === 'automation' && <AutomationTab onChange={refreshStatus} />}
          {tab === 'graph' && <GraphTab />}
          {tab === 'mcp' && <McpTab />}
          {tab === 'courses' && <CoursesTab />}
        </section>
      </main>
    </div>
  )
}
