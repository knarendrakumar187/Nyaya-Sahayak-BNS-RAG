# Learn RAG with Nyaya-Sahayak

This file is your study guide. Read it while clicking through the code.

## The problem RAG solves

LLMs (Gemini, GPT) are trained on old internet data. They may:

- mix up **IPC** and **BNS** section numbers  
- hallucinate punishments that are not in the statute  

**RAG = Retrieval-Augmented Generation**

```
User question
    ↓
Embed question → search vector DB → top matching law chunks
    ↓
Send (question + chunks) to LLM
    ↓
Answer grounded in retrieved text (+ citations)
```

You are not “training a legal model”. You are giving the model the right pages at ask-time.

---

## Pipeline pieces (and where they live)

### 1. Documents
Official BNS PDFs go in `data/raw/`. For day-one demos we ship `data/sample/bns_sample_sections.txt`.

### 2. Chunking — `backend/ingest.py`
A 500-page PDF is too big for one prompt. We split into overlapping windows (`chunk_size=800`, `overlap=150`) so a section isn’t cut awkwardly.

**Concept:** smaller chunks = more precise retrieval; too small = lost context.

### 3. Embeddings — same file, `HuggingFaceEmbeddings`
Each chunk becomes a vector (e.g. 384 numbers). Similar meaning ⇒ vectors close together.

We use a **local** model (`all-MiniLM-L6-v2`) so embeddings don’t need a paid API.

### 4. Vector store — FAISS
FAISS stores vectors and finds nearest neighbors fast. Saved under `data/processed/faiss_index/`.

### 5. Retrieval + generation — `backend/rag.py`
1. Embed the question  
2. `similarity_search` → top 4 chunks  
3. Stuff them into `prompts.py`  
4. Call Gemini/OpenAI with strict “answer only from context” rules  

### 6. Compare X-factor — `backend/compare.py`
Not pure RAG — a curated JSON table (`data/mappings/ipc_bns_map.json`) for famous mappings like **IPC 302 → BNS 103**. The LLM only explains the hit.

### 7. API — `backend/main.py`
FastAPI exposes `/api/ingest`, `/api/ask`, `/api/compare` to the React app.

### 8. UI — `frontend/src/App.tsx`
React chat for Ask + Compare. Vite proxies `/api` → `localhost:8000`.

---

## Vocabulary cheat sheet

| Term | Meaning |
|------|---------|
| LLM | Large language model that writes the answer |
| Embedding | Numeric fingerprint of text meaning |
| Vector DB / FAISS | Search engine over embeddings |
| Chunk | Piece of a document you embed & retrieve |
| Top-k | How many chunks you pull (here: 4) |
| Hallucination | Confident but wrong model output |
| Grounding | Forcing answers to stick to retrieved text |
| LangChain | Glue library for loaders, splitters, vector stores, LLMs |

---

## Practice exercises (learn by doing)

1. Change `top_k` in `backend/config.py` from 4 → 2. How do answers change?  
2. Add a new mapping to `ipc_bns_map.json` and query it in Compare.  
3. Drop a real BNS PDF into `data/raw/`, rebuild index, ask a question only that PDF can answer.  
4. Switch `LLM_PROVIDER=openai` and compare answer style.  
5. Break the system prompt on purpose (remove “don’t invent sections”) and watch hallucinations increase — then put it back.

---

## What to say in interviews

> “I built a RAG system over BNS. Documents are chunked and embedded into FAISS. At query time I retrieve the nearest statutory chunks and prompt Gemini to answer only from that context, returning source excerpts. I also shipped an IPC→BNS compare table for the transition confusion lawyers face.”

That shows you understand **retrieval**, **grounding**, and a **real domain problem** — not just calling an API.
