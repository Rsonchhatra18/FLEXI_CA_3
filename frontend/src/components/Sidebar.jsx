import { COURSES } from '../data.js'

export default function Sidebar({ status, threadId, onNewChat }) {
  const kb = status?.kb ?? { documents: '–', chunks: '–' }
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-icon">🧭</span>
        <div>
          <div className="brand-name">StudyPilot</div>
          <div className="brand-sub">Agentic RAG study assistant</div>
        </div>
      </div>

      <div className="side-section">
        <h3>Model</h3>
        <dl className="kv">
          <dt>Provider</dt><dd><code>{status?.provider ?? '…'}</code></dd>
          <dt>Main</dt><dd><code>{status?.main_model ?? '…'}</code></dd>
          <dt>Fast</dt><dd><code>{status?.fast_model ?? '…'}</code></dd>
          <dt>API key</dt>
          <dd>{status ? (status.has_key ? '✅ loaded from .env' : '❌ missing') : '…'}</dd>
        </dl>
        {status?.substitutions?.length > 0 && (
          <div className="side-note">
            ℹ️ Retired on Groq, auto-replaced:
            {status.substitutions.map((s) => (
              <div key={s.setting} className="swap">{s.configured} → {s.used.replace('openai/', '')}</div>
            ))}
          </div>
        )}
      </div>

      <div className="side-section">
        <h3>Knowledge base</h3>
        <div className="stats">
          <div className="stat"><span className="stat-value">{kb.documents}</span><span>Documents</span></div>
          <div className="stat"><span className="stat-value">{kb.chunks}</span><span>Chunks</span></div>
        </div>
      </div>

      <div className="side-section">
        <p className="side-note">Chat thread: <code>{threadId}</code></p>
        <button className="btn btn-ghost-light full" onClick={onNewChat}>🆕 New chat</button>
      </div>

      <div className="side-footer">
        <h3>Built with learnings from</h3>
        <ol>
          {COURSES.map((c) => <li key={c.short}>{c.short}</li>)}
        </ol>
      </div>
    </aside>
  )
}
