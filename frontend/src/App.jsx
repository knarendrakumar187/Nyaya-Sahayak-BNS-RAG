import { useEffect, useRef, useState } from 'react'
import {
  askQuestion,
  compareLaws,
  getHealth,
  ingestCorpus,
  listDocuments,
  lookupSection,
  uploadPdf,
} from './api'
import { AnswerBody } from './AnswerBody'
import './App.css'

const ASK_HINTS = [
  'Punishment for murder under BNS?',
  'What is cheating under BNS?',
  'Rash driving on a public way — which BNS section?',
  'Hit-and-run: which BNS sections apply?',
]

const COMPARE_HINTS = ['302', '498A', 'cheating', 'sedition']
const SECTION_HINTS = ['103', '106', '281', '318', '85']

const PIPELINE_STEPS = [
  { id: 'query_expansion', label: 'Expand query' },
  { id: 'multi_query_faiss', label: 'FAISS search' },
  { id: 'keyword_boost', label: 'Keyword boost' },
  { id: 'prompt_with_context', label: 'Ground prompt' },
  { id: 'llm_generate', label: 'Generate answer' },
]

function formatBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function App() {
  const [mode, setMode] = useState('ask')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [indexReady, setIndexReady] = useState(false)
  const [provider, setProvider] = useState('gemini')
  const [corpusMode, setCorpusMode] = useState(null)
  const [sourceFiles, setSourceFiles] = useState([])
  const [documents, setDocuments] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const [showHow, setShowHow] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const fileInputRef = useRef(null)
  const bottomRef = useRef(null)

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

  async function handleFiles(files) {
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

  async function copyMessage(m) {
    const parts = [m.content]
    if (m.sources?.length) {
      parts.push('\n\nSources:')
      for (const s of m.sources) {
        parts.push(
          `- ${s.source_name || 'Source'}${s.page != null ? ` p.${s.page + 1}` : ''}: ${s.excerpt}`,
        )
      }
    }
    await navigator.clipboard.writeText(parts.join('\n'))
    setCopiedId(m.id)
    window.setTimeout(() => setCopiedId(null), 1600)
  }

  async function handleFollowup(text) {
    if (/section finder/i.test(text)) {
      const m = text.match(/(\d{2,3}[A-Za-z]?)/)
      setMode('section')
      if (m) {
        setInput(m[1])
        void submit(m[1], 'section')
      }
      return
    }
    if (/^compare\b/i.test(text) || /\bIPC\b/i.test(text)) {
      setMode('compare')
      const q = text.replace(/^compare\s+/i, '')
      void submit(q, 'compare')
      return
    }
    if (/exact text of BNS Section/i.test(text)) {
      const m = text.match(/Section\s+(\d{2,3}[A-Za-z]?)/i)
      setMode('section')
      if (m) {
        setInput(m[1])
        void submit(m[1], 'section')
      }
      return
    }
    setMode('ask')
    void submit(text, 'ask')
  }

  async function submit(question, forcedMode) {
    const active = forcedMode || mode
    const q = question.trim()
    if (!q || loading) return
    if (active === 'upload') return

    setError(null)
    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: q },
    ])
    setLoading(true)

    try {
      if (active === 'ask') {
        const res = await askQuestion(q)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.answer,
            sources: res.sources,
            followups: res.followups,
            retrieval: res.retrieval,
            pipeline: res.pipeline,
            formatted: true,
          },
        ])
      } else if (active === 'compare') {
        const res = await compareLaws(q)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.explanation,
            mappings: res.mappings,
            followups: ['Ask about punishment under the BNS section', 'Open Section Finder for that BNS number'],
            formatted: true,
          },
        ])
      } else if (active === 'section') {
        const res = await lookupSection(q)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `**Section ${res.section}**\n\n${res.note}`,
            sectionMatches: res.matches,
            followups: res.found
              ? [
                  `What is the punishment under BNS Section ${res.section}?`,
                  `Compare IPC mapping for ${res.section}`,
                ]
              : ['Try Ask mode with the offence name', 'Rebuild index after uploading BNS.pdf'],
            formatted: true,
          },
        ])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e) {
    e.preventDefault()
    void submit(input)
  }

  const hints = mode === 'ask' ? ASK_HINTS : mode === 'compare' ? COMPARE_HINTS : SECTION_HINTS
  const headerCopy =
    mode === 'ask'
      ? {
          title: 'Ask the new Indian criminal law',
          body: 'Answers are grounded in retrieved text from your uploaded BNS PDF, with citations and confidence.',
        }
      : mode === 'compare'
        ? {
            title: 'Compare IPC and BNS sections',
            body: 'Look up how familiar IPC offences map into Bharatiya Nyaya Sanhita.',
          }
        : mode === 'section'
          ? {
              title: 'Find a BNS section in the PDF',
              body: 'Lexical section lookup — great when you already know the number (103, 281, 318…).',
            }
          : {
              title: 'Upload law PDFs',
              body: 'Add official BNS PDFs. We save them, chunk them, and rebuild the FAISS index.',
            }

  return (
    <div className="shell">
      <nav className="navbar">
        <a
          className="nav-brand"
          href="#top"
          onClick={(e) => {
            e.preventDefault()
            setMode('ask')
          }}
        >
          <span className="nav-brand-mark">
            Nyaya-<em>Sahayak</em>
          </span>
          <span className="nav-brand-tag">BNS RAG</span>
        </a>

        <div className="nav-links">
          {(
            [
              ['ask', 'Ask'],
              ['compare', 'Compare'],
              ['section', 'Sections'],
              ['upload', 'Upload PDF'],
            ]
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`nav-link ${mode === id ? 'active' : ''}`}
              onClick={() => setMode(id)}
            >
              {label}
            </button>
          ))}
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
          <button type="button" className="how-toggle" onClick={() => setShowHow((v) => !v)}>
            {showHow ? 'Hide how RAG works' : 'How RAG works'}
          </button>
        </header>

        {showHow && (
          <section className="how-panel">
            <ol>
              {PIPELINE_STEPS.map((step) => (
                <li key={step.id}>
                  <strong>{step.label}</strong>
                  <span>{step.id}</span>
                </li>
              ))}
            </ol>
            <p>
              Interview tip: FAISS returns L2 distance (lower = closer). We expand colloquial queries
              like “hit-and-run” into statute language before searching.
            </p>
          </section>
        )}

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
                While PDFs exist in <code>data/raw/</code>, demo sample text is skipped.
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
                <button type="button" className="action-btn" onClick={() => setMessages([])}>
                  Clear chat
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
                  <strong>
                    {mode === 'ask'
                      ? 'Start with a legal question'
                      : mode === 'compare'
                        ? 'Look up a mapping'
                        : 'Enter a section number'}
                  </strong>
                  {mode === 'ask'
                    ? 'Example: “What is the punishment for cheating under the new law?”'
                    : mode === 'compare'
                      ? 'Example: “302” or “What is 498A now?”'
                      : 'Example: 103, 281, or 318'}
                </div>
              )}

              {messages.map((m) => (
                <div key={m.id} className={`bubble ${m.role}`}>
                  {m.role === 'assistant' && m.formatted ? (
                    <AnswerBody text={m.content} />
                  ) : (
                    m.content
                  )}

                  {m.retrieval && (
                    <div className={`retrieval-meta ${m.retrieval.low_confidence ? 'warn' : 'ok'}`}>
                      {m.retrieval.low_confidence
                        ? 'Low retrieval confidence — answer may be limited by matching chunks.'
                        : `Grounded retrieval · best L2 ${m.retrieval.best_l2_distance}`}
                    </div>
                  )}

                  {m.pipeline && m.pipeline.length > 0 && (
                    <div className="mini-pipeline">
                      {m.pipeline.map((step) => (
                        <span key={step}>{step.replaceAll('_', ' ')}</span>
                      ))}
                    </div>
                  )}

                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      <div className="sources-title">Sources from corpus</div>
                      {m.sources.map((s, i) => (
                        <div
                          className={`source relevance-${s.relevance || 'low'}`}
                          key={`${m.id}-${i}`}
                        >
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

                  {m.sectionMatches && m.sectionMatches.length > 0 && (
                    <div className="sources">
                      <div className="sources-title">Matched PDF chunks</div>
                      {m.sectionMatches.map((s, i) => (
                        <div className="source relevance-high" key={`${m.id}-sec-${i}`}>
                          <span>
                            {s.source_name}
                            {s.page != null ? ` · p.${s.page + 1}` : ''}
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

                  {m.role === 'assistant' && (
                    <div className="msg-actions">
                      <button type="button" className="action-btn" onClick={() => void copyMessage(m)}>
                        {copiedId === m.id ? 'Copied' : 'Copy answer'}
                      </button>
                    </div>
                  )}

                  {m.followups && m.followups.length > 0 && (
                    <div className="followups">
                      {m.followups.map((f) => (
                        <button key={f} type="button" className="hint" onClick={() => void handleFollowup(f)}>
                          {f}
                        </button>
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
                    : mode === 'compare'
                      ? 'Enter IPC/BNS section or offence name…'
                      : 'Enter section number, e.g. 103'
                }
                disabled={loading}
              />
              <button className="send-btn" type="submit" disabled={loading || !input.trim()}>
                {loading ? '…' : mode === 'ask' ? 'Ask' : mode === 'compare' ? 'Compare' : 'Find'}
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
