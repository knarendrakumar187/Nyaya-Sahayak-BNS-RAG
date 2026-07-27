"""
Retrieval-Augmented Generation pipeline.

Flow:
1. Embed the user question
2. Retrieve top-k similar chunks from FAISS (with distances)
3. Stuff those chunks into a prompt
4. Ask the LLM to answer ONLY from that context

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

# Heuristic for all-MiniLM-L6-v2 + FAISS L2 on short legal chunks.
# Above this best-distance, we flag low confidence (great interview talking point).
LOW_CONFIDENCE_L2 = 1.35


def get_llm(settings: Settings | None = None):
    settings = settings or get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing. Add it to your .env file.")
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.2,
        )

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is missing. Add it to your .env file.")
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.2,
    )


def retrieve_with_scores(
    question: str, settings: Settings | None = None
) -> list[tuple[Document, float]]:
    settings = settings or get_settings()
    store = load_index(settings)
    return store.similarity_search_with_score(question, k=settings.top_k)


def format_context(ranked: list[tuple[Document, float]]) -> str:
    parts = []
    for i, (doc, distance) in enumerate(ranked, start=1):
        source = doc.metadata.get("source", "unknown")
        parts.append(
            f"[Source {i}: {source} | l2_distance={distance:.4f}]\n{doc.page_content}"
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
    if distance <= 0.85:
        return "high"
    if distance <= LOW_CONFIDENCE_L2:
        return "medium"
    return "low"


def ask(question: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    ranked = retrieve_with_scores(question, settings)
    context = format_context(ranked)
    best = float(ranked[0][1]) if ranked else 999.0
    low_confidence = bool((not ranked) or best > LOW_CONFIDENCE_L2)

    llm = get_llm(settings)
    guard = ""
    if low_confidence:
        guard = (
            "\n\nIMPORTANT: Retrieval confidence is LOW for this question. "
            "If the context does not clearly answer it, say you do not have enough "
            "grounded source text and do not invent section numbers."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT + guard),
        HumanMessage(content=QA_PROMPT.format(context=context, question=question)),
    ]
    response = llm.invoke(messages)

    sources = []
    for doc, distance in ranked:
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
                "excerpt": doc.page_content[:320].strip(),
                "l2_distance": round(float(distance), 4),
                "relevance": _relevance_label(float(distance)),
                "corpus_mode": str(doc.metadata.get("corpus_mode", "unknown")),
            }
        )

    meta = read_index_meta(settings) or {}
    return {
        "answer": _as_text(response.content),
        "sources": sources,
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
        },
        "pipeline": [
            "embed_query",
            "faiss_similarity_search",
            "prompt_with_context",
            "llm_generate",
        ],
    }
