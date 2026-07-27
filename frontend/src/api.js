async function parseError(res) {
  try {
    const data = await res.json()
    return data.detail || data.message || res.statusText
  } catch {
    return res.statusText
  }
}

export async function getHealth() {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listDocuments() {
  const res = await fetch('/api/documents')
  if (!res.ok) throw new Error(await parseError(res))
  const data = await res.json()
  return data.documents ?? []
}

export async function uploadPdf(file, rebuildIndex = true) {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(`/api/upload?rebuild_index=${rebuildIndex ? 'true' : 'false'}`, {
    method: 'POST',
    body,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function ingestCorpus() {
  const res = await fetch('/api/ingest', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function askQuestion(question) {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function compareLaws(query) {
  const res = await fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function lookupSection(section) {
  const res = await fetch('/api/section', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
