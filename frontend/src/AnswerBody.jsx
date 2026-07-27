/** Tiny Markdown renderer for assistant answers (bold, quotes, lists, paragraphs). */

function inlineFormat(text) {
  const parts = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let last = 0
  let m
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const token = m[0]
    if (token.startsWith('**')) parts.push({ bold: token.slice(2, -2) })
    else parts.push({ code: token.slice(1, -1) })
    last = m.index + token.length
  }
  if (last < text.length) parts.push(text.slice(last))

  return parts.map((p, i) => {
    if (typeof p === 'string') return <span key={i}>{p}</span>
    if ('bold' in p) return <strong key={i}>{p.bold}</strong>
    return <code key={i}>{p.code}</code>
  })
}

export function AnswerBody({ text }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let list = []

  const flushList = () => {
    if (!list.length) return
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="md-list">
        {list.map((item, i) => (
          <li key={i}>{inlineFormat(item)}</li>
        ))}
      </ul>,
    )
    list = []
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    const trimmed = line.trim()
    if (!trimmed) {
      flushList()
      continue
    }
    if (/^[-*]\s+/.test(trimmed)) {
      list.push(trimmed.replace(/^[-*]\s+/, ''))
      continue
    }
    flushList()
    if (trimmed.startsWith('>')) {
      blocks.push(
        <blockquote key={`q-${blocks.length}`} className="md-quote">
          {inlineFormat(trimmed.replace(/^>\s?/, ''))}
        </blockquote>,
      )
      continue
    }
    if (/^#{1,3}\s+/.test(trimmed)) {
      blocks.push(
        <p key={`h-${blocks.length}`} className="md-heading">
          {inlineFormat(trimmed.replace(/^#{1,3}\s+/, ''))}
        </p>,
      )
      continue
    }
    blocks.push(
      <p key={`p-${blocks.length}`} className="md-p">
        {inlineFormat(trimmed)}
      </p>,
    )
  }
  flushList()

  return <div className="answer-body">{blocks}</div>
}
