const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export function getApiBase() {
  return API_BASE || '(same origin — set VITE_API_BASE_URL on Vercel to your Render URL)'
}

function apiUrl(path) {
  return `${API_BASE}${path}`
}

function authHeaders(extra = {}) {
  const key = localStorage.getItem('nyaya_api_key') || ''
  const headers = { ...extra }
  if (key) headers['X-API-Key'] = key
  return headers
}

async function parseError(res) {
  try {
    const data = await res.json()
    return data.detail || data.message || res.statusText
  } catch {
    return res.statusText
  }
}

export async function getHealth() {
  const res = await fetch(apiUrl('/api/health'))
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/** Wake Render Free cold starts; retries for up to ~40s. */
export async function wakeApi(attempts = 5, delayMs = 8000) {
  let lastErr = new Error('API unreachable')
  for (let i = 0; i < attempts; i++) {
    try {
      return await getHealth()
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error(String(err))
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, delayMs))
      }
    }
  }
  throw lastErr
}

export async function listDocuments() {
  const res = await fetch(apiUrl('/api/documents'))
  if (!res.ok) throw new Error(await parseError(res))
  const data = await res.json()
  return data.documents ?? []
}

export async function deleteDocument(name) {
  const res = await fetch(apiUrl(`/api/documents/${encodeURIComponent(name)}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function uploadPdf(file, rebuildIndex = true) {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(apiUrl(`/api/upload?rebuild_index=${rebuildIndex ? 'true' : 'false'}`), {
    method: 'POST',
    headers: authHeaders(),
    body,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function ingestCorpus() {
  const res = await fetch(apiUrl('/api/ingest'), {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function startIngestJob() {
  const res = await fetch(apiUrl('/api/ingest/async'), {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getIngestStatus(jobId) {
  const res = await fetch(apiUrl(`/api/ingest/status/${encodeURIComponent(jobId)}`))
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function askQuestion(question, { language = 'en', history = [], hybrid = true } = {}) {
  const res = await fetch(apiUrl('/api/ask'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ question, language, history, hybrid }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/**
 * Stream ask via SSE. Calls onToken(text), onStatus(obj), onFinal(obj).
 */
export async function askQuestionStream(
  question,
  { language = 'en', history = [], hybrid = true, onToken, onStatus, onFinal } = {},
) {
  const res = await fetch(apiUrl('/api/ask/stream'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ question, language, history, hybrid }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  if (!res.body) throw new Error('Streaming not supported in this browser')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalPayload = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const block of parts) {
      const lines = block.split('\n')
      let event = 'message'
      const dataLines = []
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) continue
      const data = JSON.parse(dataLines.join('\n'))
      if (event === 'token') onToken?.(data.text || '')
      else if (event === 'status') onStatus?.(data)
      else if (event === 'final') {
        finalPayload = data
        onFinal?.(data)
      } else if (event === 'error') throw new Error(data.detail || 'Stream error')
    }
  }
  return finalPayload
}

export async function compareLaws(query) {
  const res = await fetch(apiUrl('/api/compare'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function lookupSection(section) {
  const res = await fetch(apiUrl('/api/section'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function runEval() {
  const res = await fetch(apiUrl('/api/eval'))
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
