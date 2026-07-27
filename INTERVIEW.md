# Nyaya-Sahayak — Interview Prep Guide

Study this before demos. Every answer maps to **this repo**.

---

## 30-second pitch (memorize)

> India replaced IPC with Bharatiya Nyaya Sanhita, so section numbers changed and generic LLMs mix them up. I built **Nyaya-Sahayak**, a full-stack RAG app: React UI, FastAPI backend, local embeddings into FAISS, Gemini for generation. Users upload official PDFs, ask questions, get **citation-backed** answers, and can **compare IPC→BNS** mappings. I also surface retrieval distances and a retrieval eval script so quality isn’t a black box.

---

## Architecture (say this while drawing)

```text
PDF / sample text
    → chunk (RecursiveCharacterTextSplitter)
    → embed (all-MiniLM-L6-v2, local)
    → FAISS index (data/processed/)

User question
    → embed query
    → top-k similar chunks (+ L2 distance)
    → prompt = system rules + context + question
    → Gemini / OpenAI
    → answer + sources (+ confidence flag)
```

Code map:

| Step | File |
|------|------|
| Upload PDF | `backend/main.py` → `/api/upload` |
| Chunk + index | `backend/ingest.py` |
| Retrieve + generate | `backend/rag.py` |
| Prompts / anti-hallucination | `backend/prompts.py` |
| IPC↔BNS table | `backend/compare.py` + `data/mappings/` |
| UI | `frontend/src/App.tsx` |

---

## Must-know Q&A

### 1. What is RAG? Why not fine-tune?

**RAG** = retrieve relevant documents at query time, then generate an answer from them.

Fine-tuning teaches style/knowledge into weights; it’s costly, slow to update when laws change, and still can hallucinate. RAG lets me **swap PDFs and rebuild the index** when BNS text updates — better for statutes.

### 2. Why not just stuff the whole PDF into the prompt?

Context limits, cost, and noise. Chunking + retrieval pulls only the relevant sections (e.g. murder → BNS 103).

### 3. What is an embedding?

A vector of numbers representing meaning. Similar legal text → nearby vectors. We use `sentence-transformers/all-MiniLM-L6-v2` **locally** so embeddings don’t need a paid API.

### 4. What is FAISS? Why FAISS over Chroma?

**FAISS** = Facebook’s library for fast vector similarity search. For a resume/demo corpus, local FAISS is simple and dependency-light. Chroma is fine too (persistent DB ergonomics); I’d mention Chroma/Pinecone for multi-user production.

### 5. What does L2 distance mean in your UI?

Our FAISS index uses **L2 distance**. **Lower = more similar**. I expose `l2_distance` and a high/medium/low label. If the best distance is above a threshold, I set `low_confidence` and tighten the prompt so the model refuses instead of inventing sections.

### 6. How do you reduce hallucinations?

1. System prompt: answer **only** from context  
2. Return source excerpts  
3. Low-confidence guard when retrieval is weak  
4. Temperature 0.2  
5. Compare feature uses a **curated JSON table** (not LLM memory) for IPC→BNS numbers

### 7. Chunk size tradeoff?

- Too large → retrieval less precise, more noise in prompt  
- Too small → lose section context  

We use ~600 chars, overlap ~80, separators that prefer section banners (`====`). Tunable in `backend/config.py`.

### 8. Why is Compare separate from RAG?

Famous mappings (302→103) are structured facts. A table is **deterministic**. RAG is for open questions over statute text. Interview gold: “right tool for the job.”

### 9. How would you evaluate this system?

Two layers:

1. **Retrieval eval** (`scripts/eval_retrieval.py`) — does the right chunk appear in top-k?  
2. **Answer eval** — faithfulness (claims supported by sources), optional LLM-as-judge later  

I’d say: fix retrieval before blaming the LLM.

### 10. What breaks in production?

- PDF parsing quality (tables/columns)  
- Outdated corpus  
- Prompt injection via uploaded PDFs  
- Rate limits / API cost  
- Multilingual queries (Hindi)  
- Legal liability — must stay “not legal advice”

Mitigations: better parsers, versioned corpora, auth, virus scan uploads, cite pages, human-in-loop for serious use.

### 11. How would you scale this?

- Managed vector DB (Pinecone / pgvector)  
- Async ingest workers  
- Cache frequent queries  
- Hybrid search (BM25 + vectors) for section numbers like “103”  
- Streaming responses over SSE/WebSockets  

### 12. Why React + FastAPI?

Clear separation: React for UX, FastAPI for ML/data pipeline. Easy to demo OpenAPI at `/docs`. Interviewers like seeing you can ship a real full-stack system, not only a notebook.

---

## Live demo script (3 minutes)

1. Open UI → show navbar Ask / Compare / Upload  
2. Ask: “Punishment for murder under BNS?” → show **Section 103** + sources + distances  
3. Compare: `302` → IPC 302 → BNS 103  
4. Upload a PDF (or explain Upload) → rebuild index  
5. Optional terminal: `python scripts/eval_retrieval.py` → show PASS score  
6. Open `backend/rag.py` and walk the 4 pipeline steps  

---

## Resume bullets (copy/adapt)

- Built a full-stack **RAG** assistant (React + FastAPI + LangChain + FAISS) for Bharatiya Nyaya Sanhita with citation-backed answers  
- Implemented PDF upload, chunking, local embeddings, and rebuildable vector index for grounded legal Q&A  
- Added IPC→BNS comparison from a curated mapping table to address post-IPC transition confusion  
- Exposed retrieval L2 distances / low-confidence guards and a retrieval evaluation script for measurable quality  

---

## Honest limitations (saying this impresses seniors)

- Sample corpus is curated for learning; production needs official Gazette PDFs  
- Mapping table is not exhaustive  
- Not a substitute for a lawyer  
- Keyword-heavy queries (“section 103”) may need hybrid search for best results  
