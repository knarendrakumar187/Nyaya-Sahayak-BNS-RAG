import { useEffect, useRef, useState } from 'react'
import {
  askQuestionStream,
  compareLaws,
  deleteDocument,
  getHealth,
  getIngestStatus,
  listDocuments,
  lookupSection,
  runEval,
  startIngestJob,
  uploadPdf,
  wakeApi,
} from './api'
import { AnswerBody } from './AnswerBody'
import { ProgressOverlay, Toast } from './ProgressUI'
import './App.css'

const ASK_HINTS = [
  'Proxy interview / impersonation — which BNS section applies?',
  'Bribery or corruption in interview selection — BNS sections?',
  'Fake job interview scam cheating candidates — which BNS section?',
  'Tampering merit list or interview scores — which law applies?',
]

const COMPARE_HINTS = ['302', '304A', '420', '498A', '419']
const SECTION_HINTS = ['319', '171', '318', '103', '281']

const PIPELINE_STEPS = [
  { id: 'hybrid_retrieve', label: 'Hybrid FAISS + keyword' },
  { id: 'injection_scrub', label: 'Scrub prompt injection' },
  { id: 'prompt_with_context', label: 'Ground prompt' },
  { id: 'llm_stream', label: 'Stream answer' },
]

function formatBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function exportMarkdown(m) {
  const parts = [`# Nyaya-Sahayak answer\n\n${m.content}\n`]
  if (m.sources?.length) {
    parts.push('\n## Sources\n')
    for (const s of m.sources) {
      parts.push(
        `- **${s.source_name || 'Source'}**${s.page != null ? ` (p.${s.page + 1})` : ''}${
          s.corpus_version ? ` · corpus \`${s.corpus_version}\`` : ''
        }: ${s.excerpt}`,
      )
    }
  }
  const blob = new Blob([parts.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `nyaya-answer-${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function App() {
  const [mode, setMode] = useState('ask')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [ingestPct, setIngestPct] = useState(0)
  const [ingestMsg, setIngestMsg] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [indexReady, setIndexReady] = useState(false)
  const [provider, setProvider] = useState('gemini')
  const [corpusMode, setCorpusMode] = useState(null)
  const [sourceFiles, setSourceFiles] = useState([])
  const [corpusVersion, setCorpusVersion] = useState(null)
  const [authRequired, setAuthRequired] = useState(false)
  const [documents, setDocuments] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const [showHow, setShowHow] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [toast, setToast] = useState(null)
  const [language, setLanguage] = useState('en')
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('nyaya_api_key') || '')
  const [evalData, setEvalData] = useState(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const fileInputRef = useRef(null)
  const bottomRef = useRef(null)

  function showToast(text, tone = 'ok') {
    setToast({ text, tone })
    window.setTimeout(() => setToast(null), 4200)
  }

  function saveApiKey(value) {
    setApiKey(value)
    if (value) localStorage.setItem('nyaya_api_key', value)
    else localStorage.removeItem('nyaya_api_key')
  }

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
      setCorpusVersion(h.corpus_version ?? null)
      setAuthRequired(Boolean(h.auth_required))
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
    if (mode === 'eval') void handleEval()
  }, [mode])

  async function pollIngest(jobId) {
    for (let i = 0; i < 120; i++) {
      const job = await getIngestStatus(jobId)
      setIngestPct(job.pct ?? 0)
      setIngestMsg(job.message || job.stage || '')
      if (job.status === 'done') return job.result
      if (job.status === 'error') throw new Error(job.error || 'Ingest failed')
      await new Promise((r) => setTimeout(r, 800))
    }
    throw new Error('Ingest timed out')
  }

  async function handleIngest() {
    setIngesting(true)
    setIngestPct(5)
    setIngestMsg('Waking API…')
    setError(null)
    try {
      await wakeApi()
      setIngestMsg('Starting index job…')
      const { job_id } = await startIngestJob()
      const meta = await pollIngest(job_id)
      setIndexReady(true)
      setCorpusMode(meta?.corpus_mode ?? null)
      setSourceFiles(meta?.source_files ?? [])
      setCorpusVersion(meta?.corpus_version ?? null)
      const files = (meta?.source_files ?? []).join(', ') || 'corpus'
      const msg =
        meta?.corpus_mode === 'pdf'
          ? `Index ready from ${files} — ${meta.num_chunks} searchable chunks (corpus ${meta.corpus_version || 'n/a'}).`
          : `Demo index ready — ${meta?.num_chunks} chunks. Upload a BNS PDF for real answers.`
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: msg }])
      showToast(`Index built successfully (${meta?.num_chunks} chunks)`, 'ok')
      await refreshHealth()
    } catch (err) {
      const raw = err instanceof Error ? err.message : 'Ingest failed'
      const message =
        raw === 'Failed to fetch' || /network|fetch/i.test(raw)
          ? 'Rebuild failed on Render Free (timeout/memory). Redeploy the API so the pre-built sample index is included, then refresh /api/health — index_ready should become true without Rebuild.'
          : raw
      setError(message)
      showToast(message, 'error')
    } finally {
      setIngesting(false)
      setIngestPct(0)
      setIngestMsg('')
    }
  }

  async function handleDelete(name) {
    try {
      await deleteDocument(name)
      showToast(`Deleted ${name}`, 'ok')
      await refreshDocs()
      await refreshHealth()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed'
      setError(message)
      showToast(message, 'error')
    }
  }

  async function handleEval() {
    setEvalLoading(true)
    setError(null)
    try {
      setEvalData(await runEval())
    } catch (err) {
      setEvalData(null)
      setError(err instanceof Error ? err.message : 'Eval failed')
    } finally {
      setEvalLoading(false)
    }
  }

  async function handleFiles(files) {
    if (!files || files.length === 0) return
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length === 0) {
      setError('Please upload PDF files only.')
      return
    }

    const tooBig = pdfs.find((f) => f.size > 8 * 1024 * 1024)
    if (tooBig) {
      const msg =
        `“${tooBig.name}” is larger than 8 MB. Render Free often times out on big Gazette PDFs. Use the pre-built sample index (Ask after API health shows index_ready:true), or upload a short PDF excerpt under 8 MB.`
      setError(msg)
      showToast(msg, 'error')
      return
    }

    setUploading(true)
    setIngesting(true)
    setIngestPct(5)
    setIngestMsg('Waking Render API (can take up to 1 min)…')
    setError(null)
    try {
      const health = await wakeApi()
      setIngestPct(20)
      const results = []
      for (const file of pdfs) {
        setIngestMsg(`Uploading ${file.name}…`)
        results.push(await uploadPdf(file, false))
      }
      await refreshDocs()
      setIngestPct(40)
      setIngestMsg('PDF saved. Building index (may fail on Free RAM)…')

      try {
        const { job_id } = await startIngestJob()
        const meta = await pollIngest(job_id)
        setIndexReady(true)
        setCorpusMode(meta?.corpus_mode ?? 'pdf')
        setSourceFiles(meta?.source_files ?? [])
        setCorpusVersion(meta?.corpus_version ?? null)
        showToast(`Indexed ${meta?.num_chunks ?? ''} chunks`, 'ok')
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Uploaded and indexed ${results.map((r) => r.filename).join(', ')} (${meta?.num_chunks} chunks).`,
          },
        ])
      } catch {
        // Upload succeeded; live index build often OOMs on Render Free
        showToast('PDF uploaded, but live indexing failed on Free tier. Use sample index or redeploy API with pre-built index.', 'error')
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content:
              `Saved ${results.map((r) => r.filename).join(', ')}, but indexing timed out/OOM on Render Free. ` +
              (health?.index_ready
                ? 'Your pre-built sample index is still available for Ask.'
                : 'Redeploy the API so the sample index is baked in, then check /api/health for index_ready:true.'),
          },
        ])
      }
      await refreshHealth()
      setMode('ask')
    } catch (err) {
      const raw = err instanceof Error ? err.message : 'Upload failed'
      const message =
        raw === 'Failed to fetch' || /network|fetch/i.test(raw)
          ? 'Cannot reach Render API. Open https://nyaya-sahayak-api.onrender.com/api/health , wait until it loads, then retry. Skip large PDF uploads on Free — use the sample index.'
          : raw
      setError(message)
      showToast(message, 'error')
    } finally {
      setUploading(false)
      setIngesting(false)
      setIngestPct(0)
      setIngestMsg('')
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

  function historyForAsk(prevMessages) {
    return prevMessages
      .filter((m) => m.role === 'user' || (m.role === 'assistant' && m.formatted))
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }))
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
    if (active === 'upload' || active === 'eval') return

    setError(null)
    setInput('')
    const userMsg = { id: crypto.randomUUID(), role: 'user', content: q }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      if (active === 'ask') {
        const streamId = crypto.randomUUID()
        setMessages((prev) => [
          ...prev,
          {
            id: streamId,
            role: 'assistant',
            content: '',
            formatted: true,
            streaming: true,
          },
        ])

        const history = historyForAsk([...messages, userMsg])
        const final = await askQuestionStream(q, {
          language,
          history,
          hybrid: true,
          onToken: (text) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === streamId ? { ...m, content: (m.content || '') + text } : m)),
            )
          },
        })

        setMessages((prev) =>
          prev.map((m) =>
            m.id === streamId
              ? {
                  ...m,
                  content: final?.answer ?? m.content,
                  sources: final?.sources,
                  followups: final?.followups,
                  retrieval: final?.retrieval,
                  pipeline: final?.pipeline,
                  corpus: final?.corpus,
                  streaming: false,
                  formatted: true,
                }
              : m,
          ),
        )
      } else if (active === 'compare') {
        const res = await compareLaws(q)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.explanation,
            mappings: res.mappings,
            followups: [
              'Ask about punishment under the BNS section',
              'Open Section Finder for that BNS number',
            ],
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
          : mode === 'eval'
            ? {
                title: 'Retrieval eval dashboard',
                body: 'Hit@k style checks — does the right section land in top retrieved chunks?',
              }
            : {
                title: 'Upload law PDFs',
                body: 'Add official BNS PDFs. We save them, chunk them, and rebuild the FAISS index.',
              }

  return (
    <div className="shell">
      <ProgressOverlay
        kind={uploading ? 'upload' : ingesting ? 'ingest' : loading ? 'ask' : null}
        busy={uploading || ingesting || loading}
        detail={ingesting ? `${ingestPct}% · ${ingestMsg}` : undefined}
      />
      <Toast text={toast?.text} tone={toast?.tone} onClose={() => setToast(null)} />

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
              ['eval', 'Eval'],
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
            {ingesting || uploading
              ? 'Working… please wait'
              : indexReady
                ? corpusMode === 'pdf'
                  ? `Ready · ${sourceFiles[0] || 'PDF'}${corpusVersion ? ` · ${corpusVersion}` : ''} · ${provider}`
                  : `Ready · sample text · ${provider}`
                : 'Index not built yet'}
          </span>
        </div>
      </nav>

      <div className="app" id="top">
        <header className="page-header">
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
              Interview tip: FAISS returns L2 distance (lower = closer). Hybrid keyword boost recovers
              colloquial queries. Chunks are scrubbed for prompt-injection patterns before the LLM sees them.
            </p>
          </section>
        )}

        {mode === 'upload' ? (
          <section className="panel upload-panel">
            {(authRequired || apiKey) && (
              <div className="api-key-row">
                <label htmlFor="api-key">X-API-Key (required when server has API_KEY set)</label>
                <input
                  id="api-key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => saveApiKey(e.target.value)}
                  placeholder="Paste API key for upload / ingest / delete"
                />
              </div>
            )}

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
              <strong>{uploading ? 'Working on your PDF…' : 'Drop your BNS / IPC PDF here'}</strong>
              <span>
                {uploading
                  ? 'Indexing can take about 1 minute — please keep this tab open'
                  : 'or click to browse · PDF only · max 40 MB'}
              </span>
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
                {ingesting ? `Building… ${ingestPct}%` : 'Rebuild index'}
              </button>
              <p className="upload-hint">
                <strong>Render Free tip:</strong> skip big Gazette PDFs (they time out). Redeploy the API so
                the sample index is baked in, confirm <code>index_ready: true</code> on health, then use Ask.
                Only upload PDFs under ~8 MB.
                {corpusVersion ? (
                  <>
                    {' '}
                    Corpus version: <code>{corpusVersion}</code>
                  </>
                ) : null}
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
                      <button type="button" className="action-btn danger" onClick={() => void handleDelete(d.name)}>
                        Delete
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        ) : mode === 'eval' ? (
          <section className="panel eval-panel">
            <div className="eval-toolbar">
              <div className="eval-toolbar-copy">
                <p className="eval-kicker">Retrieval quality</p>
                <h2>Hit@k checklist</h2>
              </div>
              <button
                type="button"
                className="tool-btn primary"
                onClick={() => void handleEval()}
                disabled={evalLoading}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M4.5 12a7.5 7.5 0 0 1 12.7-5.4M19.5 12a7.5 7.5 0 0 1-12.7 5.4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M17.2 3.8v4.2h-4.2M6.8 20.2v-4.2h4.2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                {evalLoading ? 'Running…' : 'Re-run eval'}
              </button>
            </div>

            {evalData ? (
              <div className="eval-body">
                <div
                  className={`eval-score-card tone-${
                    evalData.score_pct >= 80 ? 'good' : evalData.score_pct >= 50 ? 'mid' : 'bad'
                  }`}
                >
                  <div
                    className="eval-ring"
                    style={{
                      '--score': `${evalData.score_pct}`,
                    }}
                  >
                    <div className="eval-ring-inner">
                      <strong>{evalData.score_pct}%</strong>
                      <span>score</span>
                    </div>
                  </div>
                  <div className="eval-score-meta">
                    <p className="eval-score-title">
                      {evalData.passed} of {evalData.total} cases retrieved correctly
                    </p>
                    <p className="eval-score-sub">{evalData.metric}</p>
                    <div className="eval-bar" aria-hidden="true">
                      <span style={{ width: `${evalData.score_pct}%` }} />
                    </div>
                    <div className="eval-stat-row">
                      <span className="eval-stat pass">{evalData.passed} pass</span>
                      <span className="eval-stat fail">{evalData.total - evalData.passed} fail</span>
                    </div>
                  </div>
                </div>

                <ul className="eval-cases">
                  {evalData.cases?.map((c, idx) => (
                    <li key={c.question} className={c.pass ? 'pass' : 'fail'}>
                      <div className="eval-case-top">
                        <span className={`eval-badge ${c.pass ? 'pass' : 'fail'}`}>
                          {c.pass ? 'Pass' : 'Fail'}
                        </span>
                        <span className="eval-case-num">Case {idx + 1}</span>
                        <span className="eval-expect">expects Section {c.expect}</span>
                        {c.best_l2 != null && (
                          <span className="eval-l2">L2 {c.best_l2}</span>
                        )}
                      </div>
                      <p className="eval-case-q">{c.question}</p>
                      {c.top_excerpt ? (
                        <p className="eval-case-excerpt">{c.top_excerpt}…</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="eval-empty">
                <strong>{evalLoading ? 'Running retrieval checks…' : 'No eval results yet'}</strong>
                <p>{evalLoading ? 'Searching the FAISS index for each gold case.' : 'Click Re-run eval to score retrieval.'}</p>
              </div>
            )}
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
                {mode === 'ask' && (
                  <div className="lang-toggle" role="group" aria-label="Answer language">
                    <span className="lang-label">Answer</span>
                    <div className="lang-pills">
                      <button
                        type="button"
                        className={language === 'en' ? 'active' : ''}
                        onClick={() => setLanguage('en')}
                      >
                        English
                      </button>
                      <button
                        type="button"
                        className={language === 'hi' ? 'active' : ''}
                        onClick={() => setLanguage('hi')}
                      >
                        हिंदी
                      </button>
                    </div>
                  </div>
                )}
                <button
                  type="button"
                  className="tool-btn ghost"
                  onClick={() => setMessages([])}
                  title="Clear conversation"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M5 7h14M9 7V5.8A1.8 1.8 0 0 1 10.8 4h2.4A1.8 1.8 0 0 1 15 5.8V7m-7.5 0 0.7 11.2A1.8 1.8 0 0 0 10 20h4a1.8 1.8 0 0 0 1.8-1.8L16.5 7"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Clear
                </button>
                <button
                  type="button"
                  className="tool-btn accent"
                  onClick={() => void handleIngest()}
                  disabled={ingesting || uploading || loading}
                  title="Usually takes 45–90 seconds for BNS.pdf"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M4 12a8 8 0 0 1 13.5-5.8M20 12a8 8 0 0 1-13.5 5.8"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                    />
                    <path
                      d="M17 4.5v4h-4M7 19.5v-4h4"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  {ingesting ? `${ingestPct}%` : 'Rebuild'}
                </button>
              </div>
            </div>

            <div className="thread">
              {messages.length === 0 && (
                <div className="empty">
                  <strong>
                    {mode === 'ask'
                      ? 'Ask anything about BNS'
                      : mode === 'compare'
                        ? 'Compare old IPC → new BNS'
                        : 'Find a section by number'}
                  </strong>
                  {mode === 'ask'
                    ? 'Tip: the 4 interview chips use a fast FAQ path (work without a PDF). For PDF-grounded answers, upload BNS.pdf then Rebuild — or ask something like “rash driving punishment”.'
                    : mode === 'compare'
                      ? 'Try 302, 420, 419, or 498A'
                      : 'Try 103 (murder), 281 (rash driving), or 318 (cheating)'}
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
                      {m.retrieval.metric === 'faq_fast_path' || m.retrieval.retrieval_mode === 'faq'
                        ? 'FAQ demo answer (works without uploading a PDF)'
                        : m.retrieval.low_confidence
                          ? 'Weak match in PDF — answer may be limited'
                          : `Answer grounded · ${m.retrieval.retrieval_mode || 'faiss'}${
                              m.corpus?.corpus_version ? ` · corpus ${m.corpus.corpus_version}` : ''
                            }`}
                    </div>
                  )}

                  {m.pipeline && m.pipeline.length > 0 && (
                    <details className="tech-details">
                      <summary>Technical details</summary>
                      <div className="mini-pipeline">
                        {m.pipeline.map((step) => (
                          <span key={step}>{step.replaceAll('_', ' ')}</span>
                        ))}
                      </div>
                      {m.retrieval?.best_l2_distance != null && (
                        <p className="tech-note">Best match score (L2): {m.retrieval.best_l2_distance}</p>
                      )}
                    </details>
                  )}

                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      <div className="sources-title">Cited from PDF</div>
                      {m.sources.map((s, i) => (
                        <div
                          className={`source relevance-${s.relevance || 'medium'}`}
                          key={`${m.id}-${i}`}
                        >
                          <span>
                            {s.source_name || 'BNS.pdf'}
                            {s.page != null ? ` · Page ${s.page + 1}` : ''}
                            {s.corpus_version ? ` · ${s.corpus_version}` : ''}
                            {s.relevance === 'high'
                              ? ' · Strong match'
                              : s.relevance === 'medium'
                                ? ' · Related'
                                : ' · Possible match'}
                          </span>
                          <p>{s.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {m.sectionMatches && m.sectionMatches.length > 0 && (
                    <div className="sources">
                      <div className="sources-title">Matched PDF text</div>
                      {m.sectionMatches.map((s, i) => (
                        <div className="source relevance-high" key={`${m.id}-sec-${i}`}>
                          <span>
                            {s.source_name}
                            {s.page != null ? ` · Page ${s.page + 1}` : ''}
                          </span>
                          <p>{s.excerpt}</p>
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

                  {m.role === 'assistant' && !m.streaming && (
                    <div className="msg-actions">
                      <button type="button" className="action-btn" onClick={() => void copyMessage(m)}>
                        {copiedId === m.id ? 'Copied' : 'Copy answer'}
                      </button>
                      <button type="button" className="action-btn" onClick={() => exportMarkdown(m)}>
                        Export .md
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

              {loading && messages[messages.length - 1]?.streaming !== true && (
                <div className="bubble assistant loading-bubble">
                  <span className="typing-dots" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </span>
                  Searching your PDF and writing an answer…
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <form className="composer" onSubmit={onSubmit}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  mode === 'ask'
                    ? language === 'hi'
                      ? 'BNS के बारे में हिंदी में पूछें…'
                      : 'Ask about BNS punishment, offence, or procedure…'
                    : mode === 'compare'
                      ? 'Enter IPC/BNS section or offence name…'
                      : 'Enter section number, e.g. 103'
                }
                disabled={loading}
              />
              <button
                className="send-btn"
                type="submit"
                disabled={loading || ingesting || uploading || !input.trim()}
              >
                {loading ? 'Working…' : mode === 'ask' ? 'Ask' : mode === 'compare' ? 'Compare' : 'Find'}
              </button>
            </form>
          </section>
        )}

        {error && <div className="error">{error}</div>}

        <p className="footer-note">
          {corpusMode === 'pdf'
            ? `Grounded on uploaded PDF(s): ${sourceFiles.join(', ') || 'data/raw'}${
                corpusVersion ? ` · version ${corpusVersion}` : ''
              }. Not legal advice.`
            : 'Using built-in sample BNS text (not a full Gazette PDF). Not legal advice.'}
        </p>
      </div>
    </div>
  )
}

export default App
