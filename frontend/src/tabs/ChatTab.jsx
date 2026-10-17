import { useEffect, useRef, useState } from 'react'
import { errorText, streamNDJSON } from '../api.js'
import { EXAMPLES } from '../data.js'
import AgentTrace from '../components/AgentTrace.jsx'
import Markdown from '../components/Markdown.jsx'
import RouteBadge from '../components/RouteBadge.jsx'

function AssistantMessage({ msg }) {
  if (msg.error) return <div className="alert error">{msg.error}</div>
  const r = msg.result
  return (
    <>
      <RouteBadge route={r.route} />
      <Markdown>{r.answer}</Markdown>
      {r.sources.length > 0 && (
        <div className="sources">
          <span className="muted">📎 Sources:</span>
          {r.sources.map((s) => <span key={s} className="chip">{s}</span>)}
        </div>
      )}
      <AgentTrace result={r} />
    </>
  )
}

export default function ChatTab({ messages, setMessages, threadId, onAnswered }) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [liveSteps, setLiveSteps] = useState([]) // trace steps streamed while the agent works
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, liveSteps])

  async function ask(text) {
    const question = text.trim()
    if (!question || busy) return
    setInput('')
    setBusy(true)
    setLiveSteps([])
    setMessages((m) => [...m, { role: 'user', content: question }])

    let reply = { role: 'assistant', error: 'No answer received.' }
    try {
      await streamNDJSON('/api/chat', { question, thread_id: threadId }, (ev) => {
        if (ev.type === 'step') setLiveSteps((s) => [...s, ev])
        if (ev.type === 'result') reply = { role: 'assistant', result: ev }
        if (ev.type === 'error') reply = { role: 'assistant', error: ev.error }
      })
    } catch (e) {
      reply = { role: 'assistant', error: errorText(e) }
    }
    setMessages((m) => [...m, reply])
    setLiveSteps([])
    setBusy(false)
    onAnswered?.()
  }

  return (
    <div className="card chat-card">
      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && !busy && (
          <div className="empty">
            <div className="empty-icon">🧭</div>
            <h2>Ask StudyPilot anything</h2>
            <p className="muted">
              Questions about your notes are answered with citations (corrective + self-RAG).
              Maths, facts and notes go through the tool agent. Every answer shows its full agent trace.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`msg ${msg.role}`}>
            <div className="avatar">{msg.role === 'user' ? '🧑‍🎓' : '🧭'}</div>
            <div className="bubble">
              {msg.role === 'user' ? <p>{msg.content}</p> : <AssistantMessage msg={msg} />}
            </div>
          </div>
        ))}

        {busy && (
          <div className="msg assistant">
            <div className="avatar">🧭</div>
            <div className="bubble thinking">
              <div className="thinking-head"><span className="spinner" /> Agent is working…</div>
              <ul className="live-steps">
                {liveSteps.map((s, i) => (
                  <li key={i}><span className="tick">✓</span><code>{s.node}</code> <span className="muted">{s.detail}</span></li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      <div className="composer">
        <div className="examples">
          <span className="muted">Try:</span>
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip-btn" disabled={busy} onClick={() => ask(ex)}>{ex}</button>
          ))}
        </div>
        <form className="input-row" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your notes, do maths, look something up, or save a note…"
            disabled={busy}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>Send ➤</button>
        </form>
      </div>
    </div>
  )
}
