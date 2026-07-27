"""
Retrieval-Augmented Generation pipeline (speed-tuned).

Fast path:
1. Cache FAISS + embeddings in memory
2. Search original query first
3. Only expand / keyword-boost if the first hit is weak
"""

from __future__ import annotations

from collections.abc import Generator, Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from backend.config import Settings, get_settings
from backend.faq import match_faq
from backend.ingest import load_index, read_index_meta
from backend.prompts import QA_PROMPT, SYSTEM_PROMPT
from backend.query_expand import expand_queries, keyword_terms
from backend.sections import find_section
from backend.security import scrub_chunk_text
from backend.text_clean import clean_excerpt

LOW_CONFIDENCE_L2 = 1.28
# If first-pass retrieval is this good, skip expensive multi-query expansion.
FAST_HIT_L2 = 1.05


@lru_cache(maxsize=2)
def _llm_cached(provider: str, model: str, api_key: str):
    if provider == "openai":
        return ChatOpenAI(model=model, api_key=api_key, temperature=0.15, max_tokens=700)
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.15,
        max_output_tokens=700,
    )


def get_llm(settings: Settings | None = None):
    settings = settings or get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing. Add it to your .env file.")
        return _llm_cached("openai", "gpt-4o-mini", settings.openai_api_key)

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is missing. Add it to your .env file.")
    return _llm_cached("gemini", settings.gemini_model, settings.google_api_key)


def _doc_key(doc: Document) -> str:
    page = doc.metadata.get("page")
    return f"{doc.metadata.get('source')}::{page}::{hash(doc.page_content[:180])}"


def _merge(merged: dict, doc: Document, distance: float) -> None:
    key = _doc_key(doc)
    dist = float(distance)
    if key not in merged or dist < merged[key][1]:
        merged[key] = (doc, dist)


def _keyword_search(store, terms: list[str], limit: int = 4) -> list[tuple[Document, float]]:
    if not terms:
        return []
    docstore = getattr(store, "docstore", None)
    raw = getattr(docstore, "_dict", None) if docstore is not None else None
    if not isinstance(raw, dict):
        return []

    lowered = [t.lower() for t in terms[:6]]
    scored: list[tuple[Document, float, int]] = []
    for doc in raw.values():
        if not isinstance(doc, Document):
            continue
        text = doc.page_content.lower()
        hits = sum(1 for t in lowered if t in text)
        if hits <= 0:
            continue
        distance = max(0.55, 1.15 - 0.12 * hits)
        scored.append((doc, distance, hits))

    scored.sort(key=lambda x: (-x[2], x[1]))
    return [(doc, dist) for doc, dist, _ in scored[:limit]]


def retrieve_with_scores(
    question: str,
    settings: Settings | None = None,
    *,
    hybrid: bool = True,
    top_k: int | None = None,
) -> tuple[list[tuple[Document, float]], list[str], dict[str, Any]]:
    settings = settings or get_settings()
    store = load_index(settings)
    top_k = top_k or settings.top_k
    merged: dict[str, tuple[Document, float]] = {}
    used_keyword = False

    # Dense path: FAISS
    first = store.similarity_search_with_score(question, k=top_k)
    for doc, distance in first:
        _merge(merged, doc, distance)

    best = float(first[0][1]) if first else 999.0
    queries_used = [question]

    # Hybrid / slow path when dense hit is weak
    if hybrid and best > FAST_HIT_L2:
        extras = expand_queries(question)[1 : settings.max_expand_queries]
        for q in extras:
            queries_used.append(q)
            for doc, distance in store.similarity_search_with_score(q, k=max(3, top_k - 1)):
                _merge(merged, doc, distance)

        if merged:
            best = min(dist for _, dist in merged.values())

        if best > FAST_HIT_L2:
            for doc, distance in _keyword_search(store, keyword_terms(question), limit=4):
                _merge(merged, doc, distance)
                used_keyword = True

    ranked = sorted(merged.values(), key=lambda x: x[1])[:top_k]
    info = {
        "hybrid": hybrid,
        "keyword_boost_used": used_keyword,
        "retrieval_mode": "hybrid_faiss_keyword" if used_keyword else "faiss_dense",
    }
    return ranked, queries_used, info


def format_context(ranked: list[tuple[Document, float]]) -> str:
    parts = []
    for i, (doc, distance) in enumerate(ranked, start=1):
        source = doc.metadata.get("source_name") or doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        page_bit = f" page={int(page) + 1}" if page is not None else ""
        body = scrub_chunk_text(clean_excerpt(doc.page_content, limit=420))
        parts.append(f"[Source {i}: {source}{page_bit}]\n{body}")
    return "\n\n".join(parts)


def _as_text(content) -> str:
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


def _history_block(history: Iterable[dict[str, str]] | None) -> str:
    if not history:
        return ""
    lines = ["Recent conversation (for continuity; still answer from context):"]
    for turn in list(history)[-6:]:
        role = (turn.get("role") or "user").strip().lower()
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content[:500]}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _language_instruction(language: str) -> str:
    lang = (language or "en").lower().strip()
    if lang.startswith("hi"):
        return (
            "Language: Write the full answer in clear Hindi (Devanagari). "
            "Keep section numbers and statute names in Latin/Arabic numerals."
        )
    return "Language: Write the answer in clear English."


def _sources_payload(
    ranked: list[tuple[Document, float]],
    corpus_version: str | None,
) -> list[dict]:
    strong = [(d, dist) for d, dist in ranked if dist <= LOW_CONFIDENCE_L2]
    display = strong[:3] if strong else ranked[:3]
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
                "excerpt": scrub_chunk_text(clean_excerpt(doc.page_content, limit=220)),
                "l2_distance": round(float(distance), 4),
                "relevance": _relevance_label(float(distance)),
                "corpus_mode": str(doc.metadata.get("corpus_mode", "unknown")),
                "corpus_version": corpus_version,
            }
        )
    return sources


def _faq_result(question: str, settings: Settings, meta: dict) -> dict | None:
    faq = match_faq(question)
    if not faq:
        return None

    sources = []
    try:
        from backend.ingest import _INDEX_CACHE

        warm = _INDEX_CACHE.get("store") is not None
    except Exception:
        warm = False

    if warm:
        for sec in faq.get("sections", [])[:1]:
            try:
                found = find_section(sec, settings, limit=2)
            except Exception:
                found = {"matches": []}
            for m in found.get("matches", []):
                sources.append(
                    {
                        "source": m.get("source_name", "BNS.pdf"),
                        "source_name": m.get("source_name", "BNS.pdf"),
                        "page": m.get("page"),
                        "excerpt": scrub_chunk_text(m.get("excerpt", "")),
                        "l2_distance": 0.6,
                        "relevance": "high",
                        "corpus_mode": m.get("corpus_mode", meta.get("corpus_mode", "pdf")),
                        "corpus_version": meta.get("corpus_version"),
                    }
                )

    return {
        "answer": faq["answer"],
        "sources": sources[:3],
        "followups": [
            "Proxy interview / impersonation — which BNS section applies?",
            "Bribery or corruption in interview selection — BNS sections?",
            "Fake job interview scam cheating candidates — which BNS section?",
            "Tampering merit list or interview scores — which law applies?",
        ],
        "provider": "faq+section-lookup",
        "model": "curated-fast-path",
        "corpus": {
            "mode": meta.get("corpus_mode", "unknown"),
            "source_files": meta.get("source_files", []),
            "num_chunks": meta.get("num_chunks"),
            "corpus_version": meta.get("corpus_version"),
        },
        "retrieval": {
            "top_k": settings.top_k,
            "best_l2_distance": 0.6 if sources else None,
            "low_confidence": False,
            "metric": "faq_fast_path",
            "embedding_model": settings.embedding_model,
            "queries_used": [question],
            "fast_path": True,
            "hybrid": True,
            "retrieval_mode": "faq",
        },
        "pipeline": ["faq_match", "section_lookup" if sources else "faq_only", "skip_llm"],
        "injection_scrubbed": True,
    }


def ask(
    question: str,
    settings: Settings | None = None,
    *,
    language: str = "en",
    history: list[dict[str, str]] | None = None,
    hybrid: bool = True,
) -> dict:
    settings = settings or get_settings()
    meta = read_index_meta(settings) or {}

    faq = _faq_result(question, settings, meta)
    if faq and not (language or "").lower().startswith("hi"):
        return faq

    ranked, queries_used, ret_info = retrieve_with_scores(question, settings, hybrid=hybrid)
    context = format_context(ranked)
    best = float(ranked[0][1]) if ranked else 999.0
    low_confidence = bool((not ranked) or best > LOW_CONFIDENCE_L2)

    llm = get_llm(settings)
    guard = ""
    if low_confidence:
        guard = (
            "\n\nIMPORTANT: Retrieval confidence is LOW. "
            "If context is weak, say so clearly and do NOT invent section numbers."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT + guard),
        HumanMessage(
            content=QA_PROMPT.format(
                context=context or "(no chunks retrieved)",
                question=question,
                history_block=_history_block(history),
                language_instruction=_language_instruction(language),
            )
        ),
    ]
    response = llm.invoke(messages)
    sources = _sources_payload(ranked, meta.get("corpus_version"))
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
            "corpus_version": meta.get("corpus_version"),
        },
        "retrieval": {
            "top_k": settings.top_k,
            "best_l2_distance": round(float(best), 4) if ranked else None,
            "low_confidence": low_confidence,
            "metric": "hybrid_faiss_l2+keyword (lower is more similar)",
            "embedding_model": settings.embedding_model,
            "queries_used": queries_used,
            "fast_path": len(queries_used) == 1 and not ret_info.get("keyword_boost_used"),
            **ret_info,
        },
        "pipeline": [
            "cache_faiss",
            "hybrid_retrieve" if ret_info.get("keyword_boost_used") else "fast_retrieve",
            "injection_scrub",
            "prompt_with_context",
            "llm_generate",
        ],
        "language": language,
        "injection_scrubbed": True,
    }


def ask_stream(
    question: str,
    settings: Settings | None = None,
    *,
    language: str = "en",
    history: list[dict[str, str]] | None = None,
    hybrid: bool = True,
) -> Generator[dict[str, Any], None, None]:
    """Yield SSE-friendly events: status → token* → final."""
    settings = settings or get_settings()
    meta = read_index_meta(settings) or {}

    yield {"event": "status", "data": {"stage": "retrieve", "message": "Searching corpus…"}}

    faq = _faq_result(question, settings, meta)
    if faq and not (language or "").lower().startswith("hi"):
        yield {"event": "token", "data": {"text": faq["answer"]}}
        yield {"event": "final", "data": faq}
        return

    ranked, queries_used, ret_info = retrieve_with_scores(question, settings, hybrid=hybrid)
    context = format_context(ranked)
    best = float(ranked[0][1]) if ranked else 999.0
    low_confidence = bool((not ranked) or best > LOW_CONFIDENCE_L2)

    yield {
        "event": "status",
        "data": {
            "stage": "generate",
            "message": "Generating grounded answer…",
            "best_l2": round(best, 4) if ranked else None,
        },
    }

    llm = get_llm(settings)
    guard = ""
    if low_confidence:
        guard = (
            "\n\nIMPORTANT: Retrieval confidence is LOW. "
            "If context is weak, say so clearly and do NOT invent section numbers."
        )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT + guard),
        HumanMessage(
            content=QA_PROMPT.format(
                context=context or "(no chunks retrieved)",
                question=question,
                history_block=_history_block(history),
                language_instruction=_language_instruction(language),
            )
        ),
    ]

    answer_parts: list[str] = []
    try:
        for chunk in llm.stream(messages):
            text = _as_text(getattr(chunk, "content", chunk))
            if not text:
                continue
            answer_parts.append(text)
            yield {"event": "token", "data": {"text": text}}
    except Exception:
        # Fallback if provider/stream unsupported
        response = llm.invoke(messages)
        text = _as_text(response.content)
        answer_parts = [text]
        # Fake stream in small pieces for UX
        step = max(24, len(text) // 20 or 1)
        for i in range(0, len(text), step):
            yield {"event": "token", "data": {"text": text[i : i + step]}}

    answer = "".join(answer_parts)
    sources = _sources_payload(ranked, meta.get("corpus_version"))
    followups = _suggest_followups(question, answer, sources)
    final = {
        "answer": answer,
        "sources": sources,
        "followups": followups,
        "provider": settings.llm_provider,
        "model": settings.gemini_model if settings.llm_provider == "gemini" else "gpt-4o-mini",
        "corpus": {
            "mode": meta.get("corpus_mode", "unknown"),
            "source_files": meta.get("source_files", []),
            "num_chunks": meta.get("num_chunks"),
            "corpus_version": meta.get("corpus_version"),
        },
        "retrieval": {
            "top_k": settings.top_k,
            "best_l2_distance": round(float(best), 4) if ranked else None,
            "low_confidence": low_confidence,
            "metric": "hybrid_faiss_l2+keyword (lower is more similar)",
            "embedding_model": settings.embedding_model,
            "queries_used": queries_used,
            "fast_path": len(queries_used) == 1 and not ret_info.get("keyword_boost_used"),
            **ret_info,
        },
        "pipeline": [
            "cache_faiss",
            "hybrid_retrieve" if ret_info.get("keyword_boost_used") else "fast_retrieve",
            "injection_scrub",
            "prompt_with_context",
            "llm_stream",
        ],
        "language": language,
        "injection_scrubbed": True,
    }
    yield {"event": "final", "data": final}


def _suggest_followups(question: str, answer: str, sources: list[dict]) -> list[str]:
    import re

    q = question.lower()
    suggestions: list[str] = []
    if "interview" in q or "impress" in q or "malpractice" in q:
        suggestions.extend(
            [
                "Explain murder vs culpable homicide under BNS with section numbers",
                "What are important BNS sections on medical malpractice / negligence?",
            ]
        )
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

    secs = re.findall(r"(?:section|sec\.?)\s*(\d{2,3}[A-Za-z]?)", answer, flags=re.I)
    for s in secs[:2]:
        suggestions.append(f"Show the exact text of BNS Section {s}")

    suggestions.extend(
        [
            "Which BNS sections should I study to impress in an interview?",
            "Open Section Finder for 103",
        ]
    )

    seen: set[str] = set()
    out: list[str] = []
    for s in suggestions:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:4]
