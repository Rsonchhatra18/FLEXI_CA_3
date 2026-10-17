// Thin wrappers around the StudyPilot Python API (server.py).

async function request(url, options = {}) {
  const res = await fetch(url, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`)
  return data
}

const postJSON = (url, body) =>
  request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })

/** POST a JSON body and call onEvent(obj) for every NDJSON line the server streams back. */
export async function streamNDJSON(url, body, onEvent) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status} ${res.statusText}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() // keep the incomplete last line for the next chunk
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line))
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}

/** Friendly text for any error (including "backend not running"). */
export function errorText(err) {
  if (err instanceof TypeError) return "🔌 Can't reach the StudyPilot API – is `python server.py` running?"
  return err?.message || String(err)
}

export const api = {
  status: () => request('/api/status'),
  documents: () => request('/api/documents'),
  uploadDocuments: (files) => {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    return request('/api/documents', { method: 'POST', body: form })
  },
  loadSamples: () => postJSON('/api/documents/samples'),
  deleteDocument: (name) => request(`/api/documents/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  search: (q, k) => request(`/api/search?q=${encodeURIComponent(q)}&k=${k}`),
  notes: () => request('/api/notes'),
  inbox: () => request('/api/inbox'),
  runs: () => request('/api/runs'),
  graph: () => request('/api/graph'),
  mcpDemo: () => postJSON('/api/mcp-demo'),
  mcpConfig: () => request('/api/mcp-config'),
}
