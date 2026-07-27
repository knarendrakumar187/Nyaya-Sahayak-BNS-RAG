from pathlib import Path
import re

src = Path(r"E:\cse\Projects\resume_project-NS\frontend\src")
text = (src / "App.tsx").read_text(encoding="utf-8")

text = text.replace(
    "import { FormEvent, useEffect, useRef, useState } from 'react'",
    "import { useEffect, useRef, useState } from 'react'",
)

text = re.sub(
    r"import \{\n  askQuestion,[\s\S]*?\} from '\./api'\nimport \{ AnswerBody \} from '\./AnswerBody'\n",
    """import {
  askQuestion,
  compareLaws,
  getHealth,
  ingestCorpus,
  listDocuments,
  lookupSection,
  uploadPdf,
} from './api'
import { AnswerBody } from './AnswerBody'
""",
    text,
    count=1,
)

text = re.sub(r"\ntype Mode = .*?\n\ntype ChatMessage = \{[\s\S]*?\}\n\n", "\n", text, count=1)
text = text.replace("function formatBytes(n: number)", "function formatBytes(n)")
text = text.replace("useState<Mode>('ask')", "useState('ask')")
text = text.replace("useState<ChatMessage[]>([])", "useState([])")
text = text.replace("useState<string | null>(null)", "useState(null)")
text = text.replace("useState<string[]>([])", "useState([])")
text = text.replace("useState<DocumentInfo[]>([])", "useState([])")
text = text.replace("useRef<HTMLInputElement>(null)", "useRef(null)")
text = text.replace("useRef<HTMLDivElement>(null)", "useRef(null)")
text = text.replace("async function copyMessage(m: ChatMessage)", "async function copyMessage(m)")
text = text.replace("async function handleFollowup(text: string)", "async function handleFollowup(text)")
text = text.replace(
    "async function submit(question: string, forcedMode?: Mode)",
    "async function submit(question, forcedMode)",
)
text = text.replace(
    "async function handleFiles(files: FileList | File[] | null)",
    "async function handleFiles(files)",
)
text = text.replace("function onSubmit(e: FormEvent)", "function onSubmit(e)")
text = text.replace("] as const", "]")

(src / "App.jsx").write_text(text, encoding="utf-8")
print("wrote App.jsx", len(text.splitlines()))
