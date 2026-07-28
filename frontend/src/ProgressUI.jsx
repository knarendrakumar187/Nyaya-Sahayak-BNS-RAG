import { useEffect, useState } from 'react'

const JOBS = {
  ingest: {
    title: 'Building search index',
    hint: 'Usually takes about 45–90 seconds for a full BNS PDF.',
    steps: [
      { afterSec: 0, label: 'Reading your PDF…', pct: 8 },
      { afterSec: 6, label: 'Splitting text into chunks…', pct: 22 },
      { afterSec: 12, label: 'Creating embeddings (slowest step)…', pct: 55 },
      { afterSec: 35, label: 'Saving FAISS index…', pct: 82 },
      { afterSec: 50, label: 'Finishing up…', pct: 93 },
    ],
  },
  upload: {
    title: 'Uploading & indexing PDF',
    hint: 'Prefer “Load interview demo PDF” on Free — custom embeds can take minutes or restart the API.',
    steps: [
      { afterSec: 0, label: 'Uploading PDF to server…', pct: 12 },
      { afterSec: 3, label: 'Reading PDF pages…', pct: 28 },
      { afterSec: 10, label: 'Creating embeddings (slow on Free)…', pct: 60 },
      { afterSec: 45, label: 'Saving search index…', pct: 85 },
      { afterSec: 90, label: 'Still working — Free RAM is limited…', pct: 92 },
    ],
  },
  ask: {
    title: 'Finding answer',
    hint: 'Demo chips are instant; other questions usually take a few seconds.',
    steps: [
      { afterSec: 0, label: 'Searching your PDF…', pct: 30 },
      { afterSec: 1, label: 'Preparing answer…', pct: 65 },
      { afterSec: 3, label: 'Adding citations…', pct: 85 },
      { afterSec: 8, label: 'Almost done…', pct: 94 },
    ],
  },
}

function currentStep(steps, elapsedSec) {
  let active = steps[0]
  for (const step of steps) {
    if (elapsedSec >= step.afterSec) active = step
  }
  return active
}

export function ProgressOverlay({ kind, busy, detail }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!busy) {
      setElapsed(0)
      return undefined
    }
    setElapsed(0)
    const started = Date.now()
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000))
    }, 250)
    return () => window.clearInterval(id)
  }, [busy, kind])

  if (!busy || !kind || !JOBS[kind]) return null

  const job = JOBS[kind]
  const step = currentStep(job.steps, elapsed)
  const minutes = Math.floor(elapsed / 60)
  const seconds = elapsed % 60
  const timeLabel = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`
  const pctMatch = typeof detail === 'string' ? detail.match(/^(\d+)%/) : null
  const pct = pctMatch ? Number(pctMatch[1]) : step.pct
  const label = detail || step.label

  return (
    <div className="progress-overlay" role="status" aria-live="polite">
      <div className="progress-card">
        <div className="progress-spinner" aria-hidden="true" />
        <div className="progress-copy">
          <strong>{job.title}</strong>
          <p>{label}</p>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="progress-meta">
            <span>Elapsed {timeLabel}</span>
            <span>{job.hint}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export function Toast({ text, tone = 'ok', onClose }) {
  if (!text) return null
  return (
    <div className={`toast toast-${tone}`} role="status">
      <span>{text}</span>
      <button type="button" onClick={onClose} aria-label="Dismiss">
        ×
      </button>
    </div>
  )
}
