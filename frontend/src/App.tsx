import { FormEvent, useEffect, useRef, useState } from 'react'
import {
  askQuestion,
  compareLaws,
  getHealth,
  ingestCorpus,
  listDocuments,
  uploadPdf,
  type CompareResponse,
  type DocumentInfo,
  type Source,
} from './api'
import './App.css'

type Mode = 'ask' | 'compare' | 'upload'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  mappings?: CompareResponse['mappings']
}

const ASK_HINTS = [
  'Punishment for murder under BNS?',
  'What replaced IPC 420?',
  'Hit-and-run: which BNS sections apply?',
]

const COMPARE_HINTS = ['302', '498A', 'cheating', 'sedition']

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function App() {
  const [mode, setMode] = useState<Mode>('ask')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [indexReady, setIndexReady] = useState(false)
  const [provider, setProvider] = useState('gemini')
  const [corpusMode, setCorpusMode] = useState<string | null>(null)
  const [sourceFiles, setSourceFiles] = useState<string[]>([])
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  async function refreshDocs() {
    try {
      setDocuments(await listDocuments())
    } catch {
      setDocuments([])
    }
  }

  async function refreshHealth() {
    try {
      const h = await getHealth()
      setIndexReady(h.index_ready)
      setProvider(h.llm_provider)
      setCorpusMode(h.corpus_mode ?? null)
      setSourceFiles(h.source_files ?? [])
    } catch {
      setIndexReady(false)
    }
  }

  useEffect(() => {
    void refreshHealth()
    void refreshDocs()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    if (mode === 'upload') void refreshDocs()
  }, [mode])

  async function handleIngest() {
    setIngesting(true)
    setError(null)
    try {
      const meta = await ingestCorpus()
      setIndexReady(true)
      setCorpusMode(meta.corpus_mode ?? null)
      setSourceFiles(meta.source_files ?? [])
      const files = (meta.source_files ?? []).join(', ') || 'corpus'
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            meta.corpus_mode === 'pdf'
              ? `Real PDF index ready from ${files} — ${meta.num_chunks} chunks. Demo sample is NOT used.`
              : `Demo sample index ready — ${meta.num_chunks} chunks. Upload a BNS PDF for the real corpus.`,
        },
      ])
      await refreshHealth()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingest failed')
    } finally {
      setIngesting(false)
    }
  }

  async function handleFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) return
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length === 0) {
      setError('Please upload PDF files only.')
      return
    }

    setUploading(true)
    setError(null)
    try {
      const results = []
      for (const file of pdfs) {
        results.push(await uploadPdf(file, true))
      }
      setIndexReady(true)
      await refreshDocs()
      await refreshHealth()
      const last = results[results.length - 1]
      const chunks = last.ingest?.num_chunks
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            results.length === 1
              ? `Uploaded “${results[0].filename}” and rebuilt a REAL PDF index${chunks ? ` (${chunks} chunks)` : ''}. Demo sample is skipped while PDFs exist.`
              : `Uploaded ${results.length} PDFs and rebuilt a REAL PDF index${chunks ? ` (${chunks} chunks)` : ''}.`,
        },
      ])
      setMode('ask')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function submit(question: string) {
    const q = question.trim()
    if (!q || loading) return

    setError(null)
    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: q },
    ])
    setLoading(true)

    try {
      if (mode === 'ask') {
        const res = await askQuestion(q)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.answer,
            sources: res.sources,
          },
        ])
      } else if (mode === 'compare') {
        const res = await compareLaws(q)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.explanation,
            mappings: res.mappings,
          },
        ])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void submit(input)
  }

  const hints = mode === 'ask' ? ASK_HINTS : COMPARE_HINTS
  const headerCopy =
    mode === 'ask'
      ? {
          title: 'Ask the new Indian criminal law',
          body: 'Answers are grounded in retrieved text from your uploaded PDFs and sample corpus.',
        }
      : mode === 'compare'
        ? {
            title: 'Compare IPC and BNS sections',
            body: 'Look up how familiar IPC offences map into Bharatiya Nyaya Sanhita.',
          }
        : {
            title: 'Upload law PDFs',
            body: 'Add official BNS or IPC PDFs. We save them, chunk them, and rebuild the FAISS index.',
          }

  return (
    <div className="shell">
      <nav className="navbar">
        <a className="nav-brand" href="#top" onClick={() => setMode('ask')}>
          <span className="nav-brand-mark">
            Nyaya-<em>Sahayak</em>
          </span>
          <span className="nav-brand-tag">BNS RAG</span>
        </a>

        <div className="nav-links">
          <button
            type="button"
            className={`nav-link ${mode === 'ask' ? 'active' : ''}`}
            onClick={() => setMode('ask')}
          >
            Ask
          </button>
          <button
            type="button"
            className={`nav-link ${mode === 'compare' ? 'active' : ''}`}
            onClick={() => setMode('compare')}
          >
            Compare
          </button>
          <button
            type="button"
            className={`nav-link ${mode === 'upload' ? 'active' : ''}`}
            onClick={() => setMode('upload')}
          >
            Upload PDF
          </button>
        </div>

        <div className="nav-status">
          <span className={`dot ${indexReady ? 'ok' : ''}`} />
          <span>
            {indexReady
              ? corpusMode === 'pdf'
                ? `Real PDF · ${sourceFiles[0] || 'uploaded'} · ${provider}`
                : `Demo sample · ${provider}`
              : 'Index not built'}
          </span>
        </div>
      </nav>

      <div className="app" id="top">
        <header className="page-header">
          <p className="eyebrow">Nyaya-Sahayak</p>
          <h1>{headerCopy.title}</h1>
          <p>{headerCopy.body}</p>
        </header>

        {mode === 'upload' ? (
          <section className="panel upload-panel">
            <div
              className={`dropzone ${dragOver ? 'over' : ''} ${uploading ? 'busy' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                void handleFiles(e.dataTransfer.files)
              }}
              onClick={() => !uploading && fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click()
              }}
            >
              <strong>{uploading ? 'Uploading & indexing…' : 'Drop BNS / IPC PDFs here'}</strong>
              <span>or click to browse · PDF only · max 40 MB each</span>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                multiple
                hidden
                onChange={(e) => void handleFiles(e.target.files)}
              />
            </div>

            <div className="upload-actions">
              <button
                type="button"
                className="action-btn"
                onClick={() => void handleIngest()}
                disabled={ingesting || uploading}
              >
                {ingesting ? 'Rebuilding…' : 'Rebuild index'}
              </button>
              <p className="upload-hint">
                Uploaded files are stored in <code>data/raw/</code> and indexed with the sample corpus.
              </p>
            </div>

            <div className="doc-list">
              <h2>Uploaded PDFs</h2>
              {documents.length === 0 ? (
                <p className="doc-empty">No PDFs yet. Upload an official BNS Gazette PDF to get started.</p>
              ) : (
                <ul>
                  {documents.map((d) => (
                    <li key={d.name}>
                      <span>{d.name}</span>
                      <span className="doc-size">{formatBytes(d.size_bytes)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        ) : (
          <section className="panel">
            <div className="panel-toolbar">
              <div className="hints">
                {hints.map((h) => (
                  <button key={h} type="button" className="hint" onClick={() => void submit(h)}>
                    {h}
                  </button>
                ))}
              </div>
              <div className="toolbar-actions">
                <button type="button" className="action-btn" onClick={() => setMode('upload')}>
                  Upload PDF
                </button>
                <button
                  type="button"
                  className="action-btn"
                  onClick={() => void handleIngest()}
                  disabled={ingesting}
                >
                  {ingesting ? 'Building index…' : 'Rebuild index'}
                </button>
              </div>
            </div>

            <div className="thread">
              {messages.length === 0 && (
                <div className="empty">
                  <strong>{mode === 'ask' ? 'Start with a legal question' : 'Look up a mapping'}</strong>
                  {mode === 'ask'
                    ? 'Example: “What is the punishment for cheating under the new law?”'
                    : 'Example: “302” or “What is 498A now?”'}
                </div>
              )}

              {messages.map((m) => (
                <div key={m.id} className={`bubble ${m.role}`}>
                  {m.content}
                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      {m.sources.map((s, i) => (
                        <div className="source" key={`${m.id}-${i}`}>
                          <span>
                            {s.source_name || 'Source'}
                            {s.page != null ? ` · p.${s.page + 1}` : ''}
                            {s.relevance ? ` · ${s.relevance}` : ''}
                            {s.l2_distance != null ? ` · L2 ${s.l2_distance}` : ''}
                          </span>
                          {s.excerpt}
                        </div>
                      ))}
                    </div>
                  )}
                  {m.mappings && m.mappings.length > 0 && (
                    <div className="mapping-list">
                      {m.mappings.map((row) => (
                        <div className="mapping" key={`${row.ipc_section}-${row.bns_section}`}>
                          <div className="mapping-head">
                            <strong>
                              IPC {row.ipc_section} → BNS {row.bns_section}
                            </strong>
                            <span className="pill">{row.title}</span>
                          </div>
                          {row.notes}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="bubble assistant">Retrieving context and drafting an answer…</div>
              )}
              <div ref={bottomRef} />
            </div>

            <form className="composer" onSubmit={onSubmit}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  mode === 'ask'
                    ? 'Ask about BNS punishment, offence, or procedure…'
                    : 'Enter IPC/BNS section or offence name…'
                }
                disabled={loading}
              />
              <button className="send-btn" type="submit" disabled={loading || !input.trim()}>
                {loading ? '…' : mode === 'ask' ? 'Ask' : 'Compare'}
              </button>
            </form>
          </section>
        )}

        {error && <div className="error">{error}</div>}

        <p className="footer-note">
          {corpusMode === 'pdf'
            ? `Grounded on uploaded PDF(s): ${sourceFiles.join(', ') || 'data/raw'}. Not legal advice.`
            : 'Currently on demo sample text. Upload a BNS PDF to switch to the real corpus. Not legal advice.'}
        </p>
      </div>
    </div>
  )
}

export default App
