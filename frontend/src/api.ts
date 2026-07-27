export type Source = {
  source: string
  source_name?: string
  page?: number | null
  excerpt: string
  l2_distance?: number
  relevance?: 'high' | 'medium' | 'low' | string
  corpus_mode?: string
}

export type AskResponse = {
  answer: string
  sources: Source[]
  provider: string
  model?: string
  corpus?: {
    mode?: string
    source_files?: string[]
    num_chunks?: number
  }
  retrieval?: {
    top_k: number
    best_l2_distance: number | null
    low_confidence: boolean
    metric: string
  }
}

export type Mapping = {
  ipc_section: string
  bns_section: string
  title: string
  keywords?: string[]
  notes?: string
}

export type CompareResponse = {
  query: string
  mappings: Mapping[]
  explanation: string
}

export type HealthResponse = {
  status: string
  index_ready: boolean
  llm_provider: string
  gemini_model?: string
  app: string
  corpus_mode?: string | null
  source_files?: string[]
  num_chunks?: number
}

export type DocumentInfo = {
  name: string
  size_bytes: number
}

export type UploadResponse = {
  ok: boolean
  filename: string
  size_bytes: number
  index_rebuilt: boolean
  ingest?: { num_chunks: number; num_source_docs: number }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    return data.detail || data.message || res.statusText
  } catch {
    return res.statusText
  }
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch('/api/documents')
  if (!res.ok) throw new Error(await parseError(res))
  const data = await res.json()
  return data.documents ?? []
}

export async function uploadPdf(file: File, rebuildIndex = true): Promise<UploadResponse> {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(`/api/upload?rebuild_index=${rebuildIndex ? 'true' : 'false'}`, {
    method: 'POST',
    body,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function ingestCorpus(): Promise<{
  ok: boolean
  num_chunks: number
  corpus_mode?: string
  source_files?: string[]
}> {
  const res = await fetch('/api/ingest', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function askQuestion(question: string): Promise<AskResponse> {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function compareLaws(query: string): Promise<CompareResponse> {
  const res = await fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
