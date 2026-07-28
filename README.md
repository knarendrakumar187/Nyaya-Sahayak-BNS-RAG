# Nyaya-Sahayak

**RAG assistant for Bharatiya Nyaya Sanhita (BNS)** — grounded answers from retrieved legal text, plus **IPC ↔ BNS Compare**.

Stack: **React (Vite) · FastAPI · LangChain · FAISS · Gemini 2.0 / OpenAI**

[![CI](https://github.com/knarendrakumar187/Nyaya-Sahayak-BNS-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/knarendrakumar187/Nyaya-Sahayak-BNS-RAG/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-1.3.0-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**Live demo:** [Frontend (Vercel)](https://nyaya-sahayak-bns-rag.vercel.app) · [API health (Render)](https://nyaya-sahayak-api.onrender.com/api/health)

> Render Free sleeps after idle — open the health URL first and wait for JSON (~30–90s), then use the app.

---

## Why this project

India replaced IPC with BNS. Generic chatbots often mix old and new section numbers. This app:

1. Ingests legal PDFs / curated sample text  
2. Retrieves relevant chunks (FAISS + keyword hybrid)  
3. Answers with an LLM **using only that context** (RAG)  
4. Maps famous IPC sections → BNS (Compare)

---

## Quick start (local)

### 1. Backend

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
```

Set `GOOGLE_API_KEY` in `.env` ([Google AI Studio](https://aistudio.google.com/apikey)).

```bash
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` → `:8000`.

### 3. Try it

1. Sample index works without a PDF (or upload a BNS PDF under ~15 MB)  
2. Ask: *“What is the punishment for murder under BNS?”*  
3. Compare: `302` → IPC 302 → BNS 103  

---

## Deploy (free): Vercel + Render

Step-by-step (including **fresh redeploy**): **[DEPLOYMENT.md](./DEPLOYMENT.md)**

| Part | Host | Config |
|------|------|--------|
| Frontend | Vercel | `vercel.json` + `VITE_API_BASE_URL` |
| Backend | Render Free | `render.yaml` + `Dockerfile.api` |

**Minimum:** set Render `GOOGLE_API_KEY` → set Vercel `VITE_API_BASE_URL` to your Render URL → turn off Vercel Deployment Protection for Production.

---

## Project layout

```
backend/           FastAPI + RAG pipeline
frontend/          React UI (Vite)
data/sample/       Demo BNS text (works without PDF)
data/mappings/     IPC→BNS table
tests/             API smoke tests
Dockerfile.api     Render Free API-only image
render.yaml        Render Blueprint
vercel.json        Vercel frontend build
DEPLOYMENT.md      Deploy guide
```

---

## Features

- **Ask (RAG)** — hybrid retrieval, SSE streaming, multi-turn history  
- **Compare** — IPC → BNS map  
- **Sections** — lexical section finder  
- **Eval** — Hit@k retrieval dashboard  
- **Upload** — chunked PDF ingest (Render Free–friendly)  
- **Guards** — optional API key, rate limits, injection scrub, corpus version hash  

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

Interactive docs: `/docs` on the API host.

---

## Docs

- [DEPLOYMENT.md](./DEPLOYMENT.md) — Render + Vercel  
- [LEARNING.md](./LEARNING.md) — embeddings, chunking, FAISS, RAG  
- [INTERVIEW.md](./INTERVIEW.md) — talking points  

## Resume bullets

- Built a full-stack RAG app (React + FastAPI) over BNS using LangChain and FAISS  
- Hybrid retrieval + citation-backed answers with corpus versioning  
- IPC→BNS compare for the post-2023/2024 criminal law transition  

## License

MIT — see [LICENSE](./LICENSE).
