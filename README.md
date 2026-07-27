# Nyaya-Sahayak

**RAG bot for Bharatiya Nyaya Sanhita (BNS)** — ask questions about India’s new criminal laws, grounded in retrieved text, plus an **IPC ↔ BNS Compare** feature for your resume.

Stack: **React (Vite + JavaScript) + FastAPI + LangChain + FAISS + Gemini/OpenAI**

---

## Why this project (resume angle)

India replaced IPC with BNS. Generic chatbots often confuse old vs new section numbers. This app:

1. Ingests legal PDFs / curated text  
2. Retrieves the most relevant chunks (FAISS)  
3. Answers with an LLM **using only that context** (RAG)  
4. Maps famous IPC sections → BNS (Compare)

---

## Quick start

### 1. Backend

```bash
cd E:\cse\Projects\resume_project-NS
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `GOOGLE_API_KEY` (free: [Google AI Studio](https://aistudio.google.com/apikey)).

```bash
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### 3. First query

1. Click **Build / rebuild index** (embeds sample BNS text into FAISS)  
2. Ask: *“What is the punishment for murder under BNS?”*  
3. Try Compare: `302` → should show IPC 302 → BNS 103  

Optional: put official BNS PDFs in `data/raw/` and rebuild the index.

---

## Project layout

```
backend/           FastAPI + RAG pipeline
  main.py          API routes
  ingest.py        PDF/text → chunks → FAISS
  rag.py           retrieve + generate
  compare.py       IPC↔BNS mapping
frontend/          React + JavaScript UI (Vite)
data/sample/       Demo BNS excerpts (works offline without PDFs)
data/mappings/     Curated IPC→BNS table
data/raw/          Drop official PDFs here
```

---

## Features

- **Ask (RAG)** — grounded answers from uploaded BNS PDF with citations + L2 confidence  
- **Compare** — IPC → BNS mappings (e.g. 302 → 103)  
- **Sections** — direct lexical lookup by section number  
- **Upload PDF** — ingest official Gazette PDFs and rebuild FAISS  
- **How RAG works** — pipeline explainer for demos/interviews  
- **Follow-ups + Copy** — continue the conversation and export answers  

## API

| Method | Path             | Purpose                                      |
|--------|------------------|----------------------------------------------|
| GET    | `/api/health`    | Status + whether index exists                |
| GET    | `/api/documents` | List PDFs in `data/raw/`                     |
| POST   | `/api/upload`    | Upload PDF (multipart) + rebuild FAISS index |
| POST   | `/api/ingest`    | Build FAISS index                            |
| POST   | `/api/ask`       | `{ "question": "..." }` RAG Q&A              |
| POST   | `/api/compare`   | `{ "query": "302" }` mappings                |
| POST   | `/api/section`   | `{ "section": "281" }` lexical section find  |

Docs: http://localhost:8000/docs

---

## Learn the concepts

See [LEARNING.md](./LEARNING.md) for a plain-English walkthrough of embeddings, chunking, FAISS, RAG, and how each file maps to those ideas.

---

## Resume bullet ideas

- Built a full-stack RAG app (React + FastAPI) over BNS legal text using LangChain and FAISS  
- Implemented citation-backed answers with source excerpts from retrieved chunks  
- Added IPC→BNS section comparison to address real post-2023/2024 criminal law transition confusion  
