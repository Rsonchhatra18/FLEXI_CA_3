import { useEffect, useState } from 'react'
import { api, errorText } from '../api.js'
import { GRAPH_NODES } from '../data.js'

export default function GraphTab() {
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api.graph().then(setGraph).catch((e) => setError(errorText(e))) }, [])

  return (
    <div className="grid graph-grid">
      <div className="card">
        <h2>LangGraph state machine</h2>
        {error && <div className="alert error">{error}</div>}
        {!graph && !error && <p className="muted"><span className="spinner" /> Rendering graph…</p>}
        {graph?.png && <img className="graph-img" src={`data:image/png;base64,${graph.png}`} alt="StudyPilot agent graph" />}
        {graph && !graph.png && (
          <>
            <div className="alert info">Graph image needs internet (mermaid.ink) – showing the Mermaid source instead.</div>
            <pre className="code">{graph.mermaid}</pre>
          </>
        )}
      </div>

      <div className="card">
        <h2>What each node does</h2>
        <ul className="node-list">
          {GRAPH_NODES.map(([name, technique, desc]) => (
            <li key={name}>
              <code className="node-pill">{name}</code>
              <span className="tech">{technique}</span>
              <p>{desc}</p>
            </li>
          ))}
        </ul>
        <p className="muted small">Conversation memory: MemorySaver checkpointer keyed by thread_id.</p>
      </div>
    </div>
  )
}
