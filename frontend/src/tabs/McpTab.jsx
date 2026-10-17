import { useEffect, useRef, useState } from 'react'
import { api, errorText } from '../api.js'
import { MCP_TOOLS } from '../data.js'

export default function McpTab() {
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)
  const [config, setConfig] = useState(null)
  const [copied, setCopied] = useState(false)
  const outputRef = useRef(null)

  useEffect(() => { api.mcpConfig().then(setConfig).catch(() => {}) }, [])
  useEffect(() => { if (output) outputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [output])

  async function runDemo() {
    setBusy(true); setOutput('')
    try {
      const res = await api.mcpDemo()
      setOutput(res.output)
    } catch (e) { setOutput(errorText(e)) }
    setBusy(false)
  }

  const configText = config ? JSON.stringify(config, null, 2) : ''
  const copy = () => navigator.clipboard?.writeText(configText).then(() => {
    setCopied(true); setTimeout(() => setCopied(false), 1500)
  })

  return (
    <div className="stack">
      <div className="card">
        <h2>StudyPilot as an MCP server</h2>
        <p className="muted">
          <code>mcp_server.py</code> uses the official <b>MCP Python SDK</b> (MCPServer, formerly FastMCP) over
          <b> stdio</b>, so any MCP host – Claude Desktop, an IDE, another agent – can use StudyPilot's capabilities.
        </p>
        <table className="table">
          <thead><tr><th>Type</th><th>Name</th><th>What it does</th></tr></thead>
          <tbody>
            {MCP_TOOLS.map(([type, name, desc]) => (
              <tr key={name}>
                <td><span className={`pill ${type === 'tool' ? 'ok' : 'res'}`}>{type}</span></td>
                <td><code>{name}</code></td>
                <td>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Live MCP client demo</h2>
          <button className="btn btn-primary" disabled={busy} onClick={runDemo}>
            {busy ? <><span className="spinner" /> Running…</> : '▶ Run MCP client demo'}
          </button>
        </div>
        <p className="muted">
          Runs <code>mcp_client_demo.py</code>: it launches <code>mcp_server.py</code> as a child process,
          lists its tools and calls <code>list_documents</code>, <code>search_knowledge_base</code> and <code>ask_agent</code>.
        </p>
        {busy && <p className="muted">Starting the server over stdio and calling its tools (~15 s)…</p>}
        {output && <pre className="terminal" ref={outputRef}>{output}</pre>}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Claude Desktop config</h2>
          <button className="btn" onClick={copy} disabled={!config}>{copied ? '✅ Copied' : '📋 Copy'}</button>
        </div>
        <p className="muted">Add this to <code>%APPDATA%\Claude\claude_desktop_config.json</code>, then restart Claude Desktop.</p>
        <pre className="code">{configText}</pre>
      </div>
    </div>
  )
}
