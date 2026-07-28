// Production fallback if Vercel env is missing (same name as render.yaml service).
const DEFAULT_PROD_API = 'https://nyaya-sahayak-api.onrender.com'

/**
 * Resolve API origin:
 * - Explicit VITE_API_BASE_URL always wins (set this on Vercel after Render deploy).
 * - Local `npm run dev`: relative URLs so Vite proxies /api → localhost:8000.
 * - Production build without env: hardcoded Render URL.
 */
function resolveApiBase() {
  const raw = import.meta.env.VITE_API_BASE_URL
  if (raw !== undefined && raw !== null && String(raw).trim() !== '') {
    return String(raw).replace(/\/$/, '')
  }
  if (import.meta.env.DEV) return ''
  return DEFAULT_PROD_API
}

const API_BASE = resolveApiBase()

export function getApiBase() {
  return API_BASE || '(same origin / Vite proxy)'
}

/** Health URL for wake / “Open health” links. */
export function getHealthUrl() {
  const base = API_BASE || DEFAULT_PROD_API
  return `${base}/api/health`
}

/** @deprecated use getHealthUrl */
export function getRenderHealthUrl() {
  return getHealthUrl()
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

async function fetchWithTimeout(url, options = {}, ms = 90000) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), ms)
  try {
    return await fetch(url, { ...options, signal: ctrl.signal, mode: 'cors', credentials: 'omit' })
  } finally {
    clearTimeout(timer)
  }
}

async function apiFetch(path, options = {}) {
  const health = getHealthUrl()
  try {
    return await fetchWithTimeout(apiUrl(path), options)
  } catch (err) {
    const name = err instanceof Error ? err.name : ''
    const msg = err instanceof Error ? err.message : 'network error'
    if (name === 'AbortError') {
      throw new Error(
        `Request timed out. Render Free may still be starting — open ${health}, wait for JSON, then retry.`,
      )
    }
    throw new Error(
      `Cannot reach API. Open ${health} in a new tab, wait for JSON, then retry. (${msg})`,
    )
  }
}

export async function getHealth() {
  const res = await apiFetch('/api/health')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/** Wake Render Free (can take up to ~2 min when asleep). */
export async function wakeApi(attempts = 15, delayMs = 8000) {
  let lastErr = new Error('API unreachable')
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetchWithTimeout(getHealthUrl(), {}, 90000)
      if (!res.ok) throw new Error(await parseError(res))
      return res.json()
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

export async function uploadPdfChunked(file, { onProgress } = {}) {
  const report = (pct, message) => onProgress?.({ pct, message })
  report(2, 'Waking API…')
  await wakeApi()
  report(5, 'Starting chunked upload…')

  const initRes = await apiFetch('/api/upload/init', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ filename: file.name, size_bytes: file.size }),
  })
  if (!initRes.ok) throw new Error(await parseError(initRes))
  const { upload_id } = await initRes.json()

  const buf = new Uint8Array(await file.arrayBuffer())
  const chunkSize = 100 * 1024
  const total = Math.ceil(buf.length / chunkSize) || 1

  for (let i = 0; i < total; i++) {
    const slice = buf.subarray(i * chunkSize, (i + 1) * chunkSize)
    const data_b64 = bytesToBase64(slice)
    let chunkRes
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        chunkRes = await apiFetch('/api/upload/chunk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ upload_id, index: i, data_b64 }),
        })
        if (chunkRes.ok) break
      } catch (err) {
        if (attempt === 3) throw err
        await wakeApi(3, 5000)
      }
      if (attempt < 3) await new Promise((r) => setTimeout(r, 2000))
    }
    if (!chunkRes?.ok) throw new Error(await parseError(chunkRes))
    report(8 + Math.round((80 * (i + 1)) / total), `Uploading chunk ${i + 1}/${total}…`)
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
  await wakeApi(4, 5000)
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
