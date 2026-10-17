import { useEffect, useState } from 'react'
import { api, errorText } from '../api.js'
import Markdown from '../components/Markdown.jsx'

export default function KnowledgeTab({ onChange }) {
  const [docs, setDocs] = useState([])
  const [files, setFiles] = useState([])
  const [inputKey, setInputKey] = useState(0) // bump to reset the file <input>
  const [messages, setMessages] = useState([]) // results of upload / load / delete
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [k, setK] = useState(4)
  const [hits, setHits] = useState(null)
  const [notes, setNotes] = useState([])

  const refresh = () => {
    api.documents().then(setDocs).catch((e) => setMessages([{ error: errorText(e) }]))
    api.notes().then(setNotes).catch(() => {})
    onChange?.()
  }
  useEffect(refresh, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action) {
    setBusy(true)
    try {
      const res = await action()
      setMessages(res.results ?? [res])
      refresh()
    } catch (e) {
      setMessages([{ error: errorText(e) }])
    }
    setBusy(false)
  }

  const upload = () => run(() => api.uploadDocuments(files)).then(() => {
    setFiles([])
    setInputKey((n) => n + 1)
  })
  const remove = (name) => window.confirm(`Delete ${name} from the knowledge base?`) &&
    run(() => api.deleteDocument(name))

  async function search(e) {
    e?.preventDefault()
    if (!query.trim()) return
    try { setHits(await api.search(query, k)) } catch (err) { setHits([]); setMessages([{ error: errorText(err) }]) }
  }

  return (
    <div className="grid two">
      <div className="stack">
        <div className="card">
          <h2>Add documents</h2>
          <label className={`dropzone ${files.length ? 'has-files' : ''}`}>
            <input key={inputKey} type="file" multiple accept=".pdf,.txt,.md"
              onChange={(e) => setFiles([...e.target.files])} />
            <span className="dz-icon">📄</span>
            {files.length
              ? <span>{files.map((f) => f.name).join(', ')}</span>
              : <span>Click to choose <b>PDF / TXT / MD</b> files</span>}
          </label>
          <div className="row">
            <button className="btn btn-primary" disabled={!files.length || busy} onClick={upload}>
              📥 Save to inbox &amp; ingest
            </button>
            <button className="btn" disabled={busy} onClick={() => run(api.loadSamples)}>📚 Load sample docs</button>
          </div>
          {messages.map((m, i) => m.error
            ? <div key={i} className="alert error">{m.error}</div>
            : <div key={i} className="alert info">
                {m.deleted ? `🗑️ Deleted ${m.deleted} (${m.chunks} chunks)` : `${m.source}: ${m.status} (${m.chunks} chunks)`}
              </div>)}
        </div>

        <div className="card">
          <h2>Documents</h2>
          {docs.length === 0 ? (
            <p className="muted">The knowledge base is empty – click <b>Load sample docs</b> or upload a file.</p>
          ) : (
            <table className="table">
              <thead><tr><th>Document</th><th className="num">Chunks</th><th /></tr></thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.source}>
                    <td>📄 {d.source}</td>
                    <td className="num">{d.chunks}</td>
                    <td className="num">
                      <button className="btn btn-small btn-danger" disabled={busy} onClick={() => remove(d.source)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="stack">
        <div className="card">
          <h2>Quick semantic search</h2>
          <form className="input-row" onSubmit={search}>
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. what happens when retrieval fails?" />
            <button className="btn btn-primary" type="submit" disabled={!query.trim()}>Search</button>
          </form>
          <label className="slider">
            Top-k chunks: <b>{k}</b>
            <input type="range" min="1" max="8" value={k} onChange={(e) => setK(Number(e.target.value))} />
          </label>
          {hits && hits.length === 0 && <p className="muted">No results.</p>}
          {hits?.map((h, i) => (
            <div key={i} className="hit">
              <div className="hit-head">
                <b>#{i + 1} · {h.source} p.{h.page}</b>
                <span className="muted">distance <code>{h.distance}</code> · similarity {(1 - h.distance).toFixed(2)}</span>
              </div>
              <div className="bar"><span style={{ width: `${Math.max(0, 1 - h.distance) * 100}%` }} /></div>
              <p className="hit-text">{h.text.length > 600 ? `${h.text.slice(0, 600)}…` : h.text}</p>
            </div>
          ))}
        </div>

        <div className="card">
          <h2>Saved notes <span className="muted small">(written by the save_note tool)</span></h2>
          {notes.length === 0 && <p className="muted">No notes yet – ask the agent to “save a note…”.</p>}
          {notes.map((n) => (
            <details key={n.name} className="note">
              <summary>📝 {n.name}</summary>
              <Markdown>{n.content}</Markdown>
            </details>
          ))}
        </div>
      </div>
    </div>
  )
}
