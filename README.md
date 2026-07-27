# Nyaya-Sahayak

**RAG bot for Bharatiya Nyaya Sanhita (BNS)** — ask questions about India’s new criminal laws, grounded in retrieved text, plus **IPC ↔ BNS Compare**.

Stack: **React (Vite + JS) + FastAPI + LangChain + FAISS + Gemini/OpenAI**

---

## Why this project (resume angle)

India replaced IPC with BNS. Generic chatbots often confuse old vs new section numbers. This app:

1. Ingests legal PDFs / curated text  
2. Retrieves the most relevant chunks (FAISS + keyword hybrid)  
3. Answers with an LLM **using only that context** (RAG)  
4. Maps famous IPC sections → BNS (Compare)

---

## Quick start (local)

### 1. Backend

```bash
cd E:\cse\Projects\resume_project-NS
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `GOOGLE_API_KEY` ([Google AI Studio](https://aistudio.google.com/apikey)).

```bash
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` → `:8000`.

### 3. First use

1. **Rebuild index** (sample text works; or upload a BNS PDF)  
2. Ask: *“What is the punishment for murder under BNS?”*  
3. Compare: `302` → IPC 302 → BNS 103  

---

## Deploy (free): Vercel UI + Render API

Best free setup for this project:

| Part | Host | Why |
|------|------|-----|
| **Frontend** (React/Vite) | **Vercel** | Free, fast, always on |
| **Backend** (FastAPI + FAISS) | **Render Free** | Free Python/Docker; sleeps after idle |

### Step 1 — Deploy API on Render

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**  
2. Connect **Nyaya-Sahayak-BNS-RAG** (uses `render.yaml` + `Dockerfile.api`)  
3. Set secret **`GOOGLE_API_KEY`**  
4. Deploy → copy your API URL, e.g. `https://nyaya-sahayak-api.onrender.com`  
5. Check `https://YOUR-API.onrender.com/api/health`

First wake after idle can take ~1 minute (Free spins down).

### Step 2 — Deploy UI on Vercel

1. [vercel.com/new](https://vercel.com/new) → import **Nyaya-Sahayak-BNS-RAG**  
2. Root `vercel.json` builds the `frontend/` folder  
3. **Environment Variables** (Production + Preview):

```
VITE_API_BASE_URL=https://YOUR-API.onrender.com
```

(no trailing slash)

4. Deploy → open the Vercel URL  
5. In the app: **Rebuild index** once (API must be awake)

### Local still works

```bash
# API
uvicorn backend.main:app --reload --port 8000

# UI (proxies /api → :8000 — no VITE_API_BASE_URL needed)
cd frontend && npm run dev
```

### Notes

- Render Free = **512 MB**; big PDF ingest may OOM — start with sample corpus  
- After redeploy, rebuild the index again (no free persistent disk)  
- Optional: set Render `CORS_ORIGINS` to your exact `https://….vercel.app` URL  
- **Do not commit `.env`**

---

## Project layout

```
backend/           FastAPI + RAG pipeline
frontend/          React UI (Vite)
data/sample/       Demo BNS text (works without PDF)
data/mappings/     IPC→BNS table (~40 mappings)
data/raw/          Uploaded PDFs (gitignored)
Dockerfile         Optional all-in-one (UI+API)
Dockerfile.api     Render Free API-only image
render.yaml        Render Blueprint (API)
vercel.json        Vercel frontend build
docker-compose.yml Local one-service Docker
```

---

## Features

- **Ask (RAG)** — hybrid retrieval, SSE streaming, Hindi/EN, multi-turn history  
- **Compare** — expanded IPC → BNS map  
- **Sections** — lexical section finder  
- **Eval** — Hit@k retrieval dashboard  
- **Upload** — PDF ingest, delete, async rebuild progress  
- **Guards** — optional API key, rate limits, request IDs, injection scrub, corpus version hash  

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Status / deploy health |
| GET | `/api/documents` | List PDFs |
| DELETE | `/api/documents/{name}` | Delete PDF |
| POST | `/api/upload` | Upload + rebuild |
| POST | `/api/ingest` | Sync rebuild |
| POST | `/api/ingest/async` | Async rebuild |
| GET | `/api/ingest/status/{id}` | Job progress |
| POST | `/api/ask` | RAG Q&A |
| POST | `/api/ask/stream` | SSE stream |
| POST | `/api/compare` | IPC↔BNS |
| POST | `/api/section` | Section find |
| GET | `/api/eval` | Retrieval eval |

Interactive docs: `/docs`

---

## Learn / interview

- [LEARNING.md](./LEARNING.md) — embeddings, chunking, FAISS, RAG  
- [INTERVIEW.md](./INTERVIEW.md) — talking points  

## Resume bullets

- Built a full-stack RAG app (React + FastAPI) over BNS using LangChain and FAISS  
- Hybrid retrieval + citation-backed answers with corpus versioning  
- IPC→BNS compare for post-2023/2024 criminal law transition  
