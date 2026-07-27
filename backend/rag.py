"""
Retrieval-Augmented Generation pipeline.

Flow:
1. Expand colloquial query into statute-friendly queries
2. Multi-query FAISS search + keyword boost
3. Merge / dedupe / rank chunks
4. Prompt LLM to answer ONLY from that context

Interview tip: FAISS IndexFlatL2 returns L2 distance — lower = more similar.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from backend.config import Settings, get_settings
from backend.ingest import load_index, read_index_meta
from backend.prompts import QA_PROMPT, SYSTEM_PROMPT
from backend.query_expand import expand_queries, keyword_terms

# Heuristic for all-MiniLM-L6-v2 + FAISS L2 on statute chunks.
LOW_CONFIDENCE_L2 = 1.28


def get_llm(settings: Settings | None = None):
    settings = settings or get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing. Add it to your .env file.")
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.15,
        )

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is missing. Add it to your .env file.")
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.15,
    )


def _doc_key(doc: Document) -> str:
    page = doc.metadata.get("page")
    return f"{doc.metadata.get('source')}::{page}::{hash(doc.page_content[:200])}"


def _keyword_search(store, terms: list[str], limit: int = 6) -> list[tuple[Document, float]]:
    """
    Light lexical search over FAISS docstore.
    Converts hit-counts into a synthetic L2-like distance (lower is better)
    so keyword hits can compete with vector hits.
    """
    if not terms:
        return []

    docstore = getattr(store, "docstore", None)
    raw = getattr(docstore, "_dict", None) if docstore is not None else None
    if not isinstance(raw, dict):
        return []

    scored: list[tuple[Document, float, int]] = []
    lowered = [t.lower() for t in terms]
    for doc in raw.values():
        if not isinstance(doc, Document):
            continue
        text = doc.page_content.lower()
        hits = sum(1 for t in lowered if t in text)
        if hits <= 0:
            continue
        # Prefer chunks with more legal phrase hits; map to distance ~0.55–1.10
        distance = max(0.55, 1.15 - 0.12 * hits)
        scored.append((doc, distance, hits))

    scored.sort(key=lambda x: (-x[2], x[1]))
    return [(doc, dist) for doc, dist, _ in scored[:limit]]


def retrieve_with_scores(
    question: str, settings: Settings | None = None
) -> tuple[list[tuple[Document, float]], list[str]]:
    """Multi-query vector search + keyword boost, merged by best distance."""
    settings = settings or get_settings()
    store = load_index(settings)
    queries = expand_queries(question)
    per_query_k = max(4, settings.top_k)

    merged: dict[str, tuple[Document, float]] = {}

    for q in queries:
        for doc, distance in store.similarity_search_with_score(q, k=per_query_k):
            key = _doc_key(doc)
            dist = float(distance)
            if key not in merged or dist < merged[key][1]:
                merged[key] = (doc, dist)

    for doc, distance in _keyword_search(store, keyword_terms(question), limit=8):
        key = _doc_key(doc)
        dist = float(distance)
        if key not in merged or dist < merged[key][1]:
            merged[key] = (doc, dist)

    ranked = sorted(merged.values(), key=lambda x: x[1])[: settings.top_k]
    return ranked, queries


def format_context(ranked: list[tuple[Document, float]]) -> str:
    parts = []
    for i, (doc, distance) in enumerate(ranked, start=1):
        source = doc.metadata.get("source_name") or doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        page_bit = f" page={int(page) + 1}" if page is not None else ""
        parts.append(
            f"[Source {i}: {source}{page_bit} | l2_distance={distance:.4f}]\n{doc.page_content}"
        )
    return "\n\n".join(parts)


def _as_text(content) -> str:
    """Normalize Gemini/OpenAI message content to a plain string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
        return "\n".join(p for p in parts if p).strip()
    return str(content)


def _relevance_label(distance: float) -> str:
    if distance <= 0.9:
        return "high"
    if distance <= LOW_CONFIDENCE_L2:
        return "medium"
    return "low"


def ask(question: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    ranked, queries_used = retrieve_with_scores(question, settings)
    context = format_context(ranked)
    best = float(ranked[0][1]) if ranked else 999.0
    low_confidence = bool((not ranked) or best > LOW_CONFIDENCE_L2)

    llm = get_llm(settings)
    guard = ""
    if low_confidence:
        guard = (
            "\n\nIMPORTANT: Retrieval confidence is LOW. "
            "If context is weak, say what related BNS themes appear (if any), "
            "state clearly that the exact phrase may not appear in BNS, "
            "and do NOT invent section numbers. Mention Motor Vehicles Act only "
            "as a possible allied law when the user asks about road accidents, "
            "without inventing MVA section numbers."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT + guard),
        HumanMessage(
            content=QA_PROMPT.format(
                context=context or "(no chunks retrieved)",
                question=question,
            )
        ),
    ]
    response = llm.invoke(messages)

    # Prefer showing stronger sources; keep at least 3 for transparency
    display = ranked
    strong = [(d, dist) for d, dist in ranked if dist <= LOW_CONFIDENCE_L2]
    if strong:
        display = strong[:4] if len(strong) >= 2 else ranked[:4]

    sources = []
    for doc, distance in display:
        source_path = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        if page is not None:
            page = int(page)
        sources.append(
            {
                "source": str(source_path),
                "source_name": str(
                    doc.metadata.get("source_name") or Path(str(source_path)).name
                ),
                "page": page,
                "excerpt": " ".join(doc.page_content.split())[:280],
                "l2_distance": round(float(distance), 4),
                "relevance": _relevance_label(float(distance)),
                "corpus_mode": str(doc.metadata.get("corpus_mode", "unknown")),
            }
        )

    meta = read_index_meta(settings) or {}
    followups = _suggest_followups(question, _as_text(response.content), sources)
    return {
        "answer": _as_text(response.content),
        "sources": sources,
        "followups": followups,
        "provider": settings.llm_provider,
        "model": settings.gemini_model if settings.llm_provider == "gemini" else "gpt-4o-mini",
        "corpus": {
            "mode": meta.get("corpus_mode", "unknown"),
            "source_files": meta.get("source_files", []),
            "num_chunks": meta.get("num_chunks"),
        },
        "retrieval": {
            "top_k": settings.top_k,
            "best_l2_distance": round(float(best), 4) if ranked else None,
            "low_confidence": low_confidence,
            "metric": "faiss_l2 (lower is more similar)",
            "embedding_model": settings.embedding_model,
            "queries_used": queries_used,
        },
        "pipeline": [
            "query_expansion",
            "multi_query_faiss",
            "keyword_boost",
            "prompt_with_context",
            "llm_generate",
        ],
    }


def _suggest_followups(question: str, answer: str, sources: list[dict]) -> list[str]:
    q = question.lower()
    suggestions: list[str] = []
    if "hit" in q or "rash" in q or "negligen" in q:
        suggestions.extend(
            [
                "What does BNS Section 281 say about rash driving?",
                "What is causing death by negligence under BNS Section 106?",
            ]
        )
    if "murder" in q or "103" in q:
        suggestions.extend(
            [
                "What is culpable homicide not amounting to murder under BNS?",
                "Compare IPC 302 with BNS",
            ]
        )
    if "cheat" in q or "420" in q or "318" in q:
        suggestions.append("Compare IPC 420 with BNS")
    # Pull first cited-looking section from sources/answer
    import re

    secs = re.findall(r"(?:section|sec\.?)\s*(\d{2,3}[A-Za-z]?)", answer, flags=re.I)
    for s in secs[:2]:
        suggestions.append(f"Show the exact text of BNS Section {s}")
    # Defaults
    suggestions.extend(
        [
            "Open Section Finder for 103",
            "What replaced IPC sedition?",
        ]
    )
    # de-dupe
    seen: set[str] = set()
    out: list[str] = []
    for s in suggestions:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:4]
