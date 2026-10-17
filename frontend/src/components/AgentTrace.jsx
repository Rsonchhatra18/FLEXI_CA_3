// "🔍 Agent trace" – shows exactly what the LangGraph agent did for one answer.
export default function AgentTrace({ result }) {
  const { trace = [], route = '', docs = [], query, question, tool_calls: toolCalls = [], verdict } = result

  return (
    <details className="trace">
      <summary>🔍 Agent trace <span className="muted">· {trace.length} steps</span></summary>
      <div className="trace-body">
        <div className="path">
          {trace.map((s, i) => (
            <span key={i} className="path-item">
              {i > 0 && <span className="arrow">→</span>}
              <span className="node-pill">{s.node}</span>
            </span>
          ))}
        </div>

        <dl className="facts">
          {route.startsWith('kb') && (
            <>
              <dt>Docs kept after grading</dt>
              <dd>{docs.length ? docs.map((d) => `${d.source} p.${d.page}`).join(', ') : 'none'}</dd>
            </>
          )}
          {query && query !== question && (
            <>
              <dt>Rewritten search query</dt>
              <dd><code>{query}</code></dd>
            </>
          )}
          {toolCalls.length > 0 && (
            <>
              <dt>Tools called</dt>
              <dd>
                {toolCalls.map((c, i) => (
                  <code key={i} className="tool-call">{c.name}({JSON.stringify(c.args)})</code>
                ))}
              </dd>
            </>
          )}
          {verdict && (
            <>
              <dt>Self-check verdict</dt>
              <dd>{verdict === 'yes' ? '✅ supported by the context' : '❌ not supported'}</dd>
            </>
          )}
        </dl>

        <table className="table compact">
          <thead><tr><th>#</th><th>Node</th><th>Detail</th></tr></thead>
          <tbody>
            {trace.map((s, i) => (
              <tr key={i}><td>{i + 1}</td><td><code>{s.node}</code></td><td>{s.detail}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
