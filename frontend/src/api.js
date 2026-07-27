const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export function getApiBase() {
  // Empty = same-origin /api (Vercel rewrite → Render, or Vite dev proxy)
  return API_BASE || '(same-origin /api → Render proxy)'
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

async function apiFetch(path, options = {}) {
  try {
    return await fetch(apiUrl(path), options)
  } catch (err) {
    const tip = API_BASE
      ? `Cannot reach ${API_BASE}. On Vercel, delete VITE_API_BASE_URL so /api is proxied.`
      : 'Cannot reach /api (Vercel→Render proxy). Wake https://nyaya-sahayak-api.onrender.com/api/health then retry.'
    throw new Error(`${tip} (${err instanceof Error ? err.message : 'network error'})`)
  }
}

export async function getHealth() {
  const res = await apiFetch('/api/health')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/** Wake Render Free cold starts; retries for up to ~60s. */
export async function wakeApi(attempts = 8, delayMs = 8000) {
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
  const res = await apiFetch('/api/documents')
  if (!res.ok) throw new Error(await parseError(res))
  const data = await res.json()
  return data.documents ?? []
}

export async function deleteDocument(name) {
  const res = await apiFetch(`/api/documents/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function uploadPdf(file, rebuildIndex = true) {
  const body = new FormData()
  body.append('file', file)
  const res = await apiFetch(`/api/upload?rebuild_index=${rebuildIndex ? 'true' : 'false'}`, {
    method: 'POST',
    headers: authHeaders(),
    body,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

function bytesToBase64(bytes) {
  let binary = ''
  const step = 0x8000
  for (let i = 0; i < bytes.length; i += step) {
    binary += String.fromCharCode(...bytes.subarray(i, i + step))
  }
  return btoa(binary)
}

/**
 * Chunked upload for Render Free.
 * onProgress({ pct, message })
 */
export async function uploadPdfChunked(file, { onProgress } = {}) {
  const report = (pct, message) => onProgress?.({ pct, message })
  report(5, 'Starting chunked upload…')

  const initRes = await apiFetch('/api/upload/init', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ filename: file.name, size_bytes: file.size }),
  })
  if (!initRes.ok) throw new Error(await parseError(initRes))
  const { upload_id } = await initRes.json()

  const buf = new Uint8Array(await file.arrayBuffer())
  const chunkSize = 120 * 1024
  const total = Math.ceil(buf.length / chunkSize) || 1

  for (let i = 0; i < total; i++) {
    const slice = buf.subarray(i * chunkSize, (i + 1) * chunkSize)
    const data_b64 = bytesToBase64(slice)
    let chunkRes
    for (let attempt = 0; attempt < 3; attempt++) {
      chunkRes = await apiFetch('/api/upload/chunk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ upload_id, index: i, data_b64 }),
      })
      if (chunkRes.ok) break
      if (attempt < 2) await new Promise((r) => setTimeout(r, 1500))
    }
    if (!chunkRes?.ok) throw new Error(await parseError(chunkRes))
    report(10 + Math.round((80 * (i + 1)) / total), `Uploading chunk ${i + 1}/${total}…`)
  }

  report(92, 'Finalizing PDF…')
  const doneRes = await apiFetch('/api/upload/complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ upload_id }),
  })
  if (!doneRes.ok) throw new Error(await parseError(doneRes))
  report(100, 'Upload complete')
  return doneRes.json()
}

export async function ingestCorpus() {
  const res = await apiFetch('/api/ingest', {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function startIngestJob() {
  const res = await apiFetch('/api/ingest/async', {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getIngestStatus(jobId) {
  const res = await apiFetch(`/api/ingest/status/${encodeURIComponent(jobId)}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function askQuestion(question, { language = 'en', history = [], hybrid = true } = {}) {
  const res = await apiFetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ question, language, history, hybrid }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function askQuestionStream(
  question,
  { language = 'en', history = [], hybrid = true, onToken, onStatus, onFinal } = {},
) {
  const res = await apiFetch('/api/ask/stream', {
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
  const res = await apiFetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function lookupSection(section) {
  const res = await apiFetch('/api/section', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function runEval() {
  const res = await apiFetch('/api/eval')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
