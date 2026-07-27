"""
Direct BNS section lookup (keyword scan over indexed chunks).

Interview angle: section numbers are brittle for pure vector search ("103" is tiny),
so a lexical section finder complements RAG.
"""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document

from backend.config import Settings, get_settings
from backend.ingest import load_index


def _normalize_section(section: str) -> str:
    s = section.strip().upper().replace(" ", "")
    s = re.sub(r"^(SECTION|SEC\.?|§)", "", s, flags=re.I)
    return s.strip()


def find_section(section: str, settings: Settings | None = None, limit: int = 5) -> dict:
    settings = settings or get_settings()
    target = _normalize_section(section)
    if not re.fullmatch(r"\d{1,3}[A-Z]?", target):
        raise ValueError("Use a section number like 103, 281, or 498A.")

    store = load_index(settings)
    docstore = getattr(store, "docstore", None)
    raw = getattr(docstore, "_dict", None) if docstore is not None else None
    if not isinstance(raw, dict):
        raise FileNotFoundError("Index docstore unavailable. Rebuild the index.")

    # Match patterns common in Gazette PDFs: "103.", "Section 103", "103.Whoever"
    patterns = [
        re.compile(rf"(?i)(?:^|[^\d]){re.escape(target)}\.(?=\s|[A-Z]|Whoever)"),
        re.compile(rf"(?i)section\s*{re.escape(target)}\b"),
        re.compile(rf"(?i)(?:^|[^\d]){re.escape(target)}\s+whoever"),
    ]

    hits: list[tuple[int, Document]] = []
    for doc in raw.values():
        if not isinstance(doc, Document):
            continue
        text = doc.page_content
        score = 0
        for i, pat in enumerate(patterns):
            if pat.search(text):
                score += len(patterns) - i
        if score:
            hits.append((score, doc))

    hits.sort(key=lambda x: (-x[0], x[1].metadata.get("page") or 0))
    selected = [doc for _, doc in hits[:limit]]

    chunks = []
    for doc in selected:
        page = doc.metadata.get("page")
        chunks.append(
            {
                "source_name": str(
                    doc.metadata.get("source_name")
                    or Path(str(doc.metadata.get("source", "BNS.pdf"))).name
                ),
                "page": int(page) if page is not None else None,
                "excerpt": " ".join(doc.page_content.split())[:500],
                "corpus_mode": str(doc.metadata.get("corpus_mode", "unknown")),
            }
        )

    return {
        "section": target,
        "found": bool(chunks),
        "matches": chunks,
        "note": (
            f"Found {len(chunks)} chunk(s) mentioning Section {target}."
            if chunks
            else f"No indexed chunk clearly mentions Section {target}. Try Ask mode or rebuild the index."
        ),
    }
