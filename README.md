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

## Deploy (recommended: Railway or Render + Docker)

One service = **React UI + FastAPI + FAISS** on a single URL. Uses the project `Dockerfile`.

**Needs:** ~1–2 GB RAM, `GOOGLE_API_KEY`, health path `/api/health`.

### Option A — Railway

1. Push this repo to GitHub  
2. Open [railway.app/new](https://railway.app/new) → **Deploy from GitHub** → select this repo  
3. Railway uses `railway.toml` + `Dockerfile`  
4. **Variables** → add:

| Variable | Value |
|----------|--------|
| `GOOGLE_API_KEY` | your Gemini key |
| `LLM_PROVIDER` | `gemini` |
| `SERVE_FRONTEND` | `true` |
| `CORS_ORIGINS` | `*` |

5. Optional but recommended: add a **Volume** at `/app/data` so PDFs + FAISS survive redeploys  
6. Generate a public domain → open it → **Rebuild index** (or upload BNS PDF)

### Option B — Render

1. Push this repo to GitHub  
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** (uses `render.yaml`), or **Web Service** with Docker  
3. Set the same env vars as Railway; keep `GOOGLE_API_KEY` secret  
4. Disk at `/app/data` is defined in `render.yaml`  
5. Open the `.onrender.com` URL → **Rebuild index**

### Local Docker (same image)

```bash
copy .env.example .env   # set GOOGLE_API_KEY
docker compose up --build -d
```

Open http://localhost:8000 · health: `/api/health`

### After deploy

1. `/api/health` → `"status":"ok"`  
2. UI loads on the same host  
3. **Rebuild index** once (first load can take 1–2 min for embeddings)  
4. Optional: set `API_KEY` to lock upload/delete  

**Do not commit `.env`.** Rotate any key that was ever pushed to GitHub.

---

## Project layout

```
backend/           FastAPI + RAG pipeline
frontend/          React UI (Vite)
data/sample/       Demo BNS text (works without PDF)
data/mappings/     IPC→BNS table (~40 mappings)
data/raw/          Uploaded PDFs (gitignored)
Dockerfile         Production: UI build + API
docker-compose.yml One-service deploy
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
