import { useEffect, useState } from 'react'
import { api, errorText, streamNDJSON } from '../api.js'
import { WORKFLOW_STEPS } from '../data.js'
import Markdown from '../components/Markdown.jsx'

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  URL.revokeObjectURL(url)
}

export default function AutomationTab({ onChange }) {
  const [docs, setDocs] = useState([])
  const [doc, setDoc] = useState('')
  const [steps, setSteps] = useState([])  // live step events
  const [state, setState] = useState('idle') // idle | running | done | error
  const [pack, setPack] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState([])
  const [inboxLog, setInboxLog] = useState([])
  const [inboxBusy, setInboxBusy] = useState(false)
  const [runs, setRuns] = useState([])

  const refresh = () => {
    api.documents().then((d) => { setDocs(d); setDoc((cur) => cur || d[0]?.source || '') }).catch(() => {})
    api.inbox().then(setPending).catch(() => {})
    api.runs().then(setRuns).catch(() => {})
  }
  useEffect(refresh, [])

  async function runPack() {
    setState('running'); setSteps([]); setPack(null); setError('')
    try {
      await streamNDJSON('/api/study-pack', { doc }, (ev) => {
        if (ev.type === 'step') setSteps((s) => [...s, ev])
        if (ev.type === 'result') {
          if (ev.status === 'success') { setPack(ev); setState('done') } else { setError(ev.error); setState('error') }
        }
        if (ev.type === 'error') { setError(ev.error); setState('error') }
      })
    } catch (e) { setError(errorText(e)); setState('error') }
    refresh()
  }

  async function processInbox() {
    setInboxBusy(true); setInboxLog([])
    try {
      await streamNDJSON('/api/inbox/process', {}, (ev) => {
        if (ev.type === 'step') setInboxLog((l) => [...l, `✅ ${ev.step} – ${ev.status}`])
        if (ev.type === 'result') setInboxLog((l) => [...l, ev.results.length
          ? `Processed ${ev.results.length} file(s)` : 'Inbox is empty – upload a file in the Knowledge Base tab first.'])
        if (ev.type === 'error') setInboxLog((l) => [...l, `❌ ${ev.error}`])
      })
    } catch (e) { setInboxLog([`❌ ${errorText(e)}`]) }
    setInboxBusy(false)
    refresh(); onChange?.()
  }

  // which flow chips are lit: 'trigger' as soon as we start, 'log' once the pack is saved
  const doneSteps = new Set(steps.map((s) => s.step))
  if (state !== 'idle') doneSteps.add('trigger')
  if (state === 'done') doneSteps.add('log')

  return (
    <div className="stack">
      <div className="card">
        <h2>Study Pack workflow</h2>
        <p className="muted">A deterministic multi-step automation (like an n8n flow): every step runs in order and is logged.</p>
        <div className="flow">
          {WORKFLOW_STEPS.map(([id, label], i) => (
            <span key={id} className="flow-item">
              {i > 0 && <span className="flow-arrow">▶</span>}
              <span className={`flow-step ${doneSteps.has(id) ? 'done' : ''}`}>{doneSteps.has(id) ? '✓ ' : ''}{label}</span>
            </span>
          ))}
        </div>

        <div className="row">
          <select value={doc} onChange={(e) => setDoc(e.target.value)} disabled={!docs.length}>
            {docs.length === 0 && <option>(knowledge base is empty)</option>}
            {docs.map((d) => <option key={d.source} value={d.source}>{d.source}</option>)}
          </select>
          <button className="btn btn-primary" disabled={!doc || state === 'running'} onClick={runPack}>
            ▶ Run Study Pack
          </button>
        </div>

        {state !== 'idle' && (
          <div className={`status-box ${state}`}>
            <div className="status-head">
              {state === 'running' && <><span className="spinner" /> Running study pack for {doc}…</>}
              {state === 'done' && <>✅ Study pack ready in {pack.seconds}s</>}
              {state === 'error' && <>❌ Study pack failed</>}
            </div>
            <ul>
              {steps.map((s, i) => <li key={i}>✅ <b>{s.step}</b> – {s.status}</li>)}
            </ul>
            {error && <div className="alert error">{error}</div>}
          </div>
        )}
      </div>

      {pack && (
        <div className="card">
          <div className="card-head">
            <h2>📘 Result</h2>
            <button className="btn" onClick={() => download(pack.path.split(/[\\/]/).pop(), pack.markdown)}>
              ⬇️ Download .md
            </button>
          </div>
          <div className="pack-scroll"><Markdown>{pack.markdown}</Markdown></div>
        </div>
      )}

      <div className="grid inbox-grid">
        <div className="card">
          <h2>Inbox trigger</h2>
          <p className="muted">
            Files waiting in <code>inbox/</code>: <b>{pending.join(', ') || 'none'}</b>. Each one is ingested,
            turned into a study pack, then moved to <code>inbox/processed/</code>.
          </p>
          <button className="btn" disabled={inboxBusy} onClick={processInbox}>
            {inboxBusy ? <><span className="spinner" /> Processing…</> : '📥 Process inbox'}
          </button>
          {inboxLog.length > 0 && <ul className="log">{inboxLog.map((l, i) => <li key={i}>{l}</li>)}</ul>}
        </div>

        <div className="card">
          <h2>Run history</h2>
          {runs.length === 0 ? <p className="muted">No runs yet.</p> : (
            <div className="table-scroll">
              <table className="table compact">
                <thead><tr><th>Time</th><th>Document</th><th>Status</th><th className="num">Seconds</th><th>Output</th></tr></thead>
                <tbody>
                  {runs.map((r, i) => (
                    <tr key={i}>
                      <td className="nowrap">{r.timestamp.slice(5, 16).replace('T', ' ')}</td>
                      <td>{r.doc}</td>
                      <td><span className={`pill ${r.status === 'success' ? 'ok' : 'bad'}`}>{r.status}</span></td>
                      <td className="num">{r.seconds}</td>
                      <td><code>{r.output ? r.output.replace('outputs/', '') : '–'}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
