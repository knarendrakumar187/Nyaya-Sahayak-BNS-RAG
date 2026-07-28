# Deployment Guide — Nyaya-Sahayak

**Fresh redeploy (recommended):** delete old Render + Vercel projects, push this repo, then follow Option A below.

Stack: **Render Free** (FastAPI) + **Vercel** (React).

---

## Fresh redeploy checklist

Do this when the old deploy is broken or you want a clean start.

1. **Push latest code** to GitHub (`main` on `Nyaya-Sahayak-BNS-RAG`).
2. **Render:** delete the old `nyaya-sahayak-api` (or any old) web service.
3. **Vercel:** delete the old project (or create a new one with a new name).
4. Redeploy **backend first**, then **frontend** (frontend needs the API URL).
5. Open `/api/health` → wait for JSON → open Vercel app → **Test connection** → Ask a sample question.

---

## Architecture

```
Browser ──► Vercel (React/Vite SPA)
                │
                │ HTTPS  VITE_API_BASE_URL
                ▼
         Render Free (FastAPI + FAISS sample index)
                │
                ├── Gemini API (LLM) — needs GOOGLE_API_KEY
                └── sentence-transformers (local embeddings)
```

---

## Pre-flight

- [ ] Gemini key from [Google AI Studio](https://aistudio.google.com/apikey)
- [ ] Repo on GitHub includes `render.yaml`, `Dockerfile.api`, `vercel.json`
- [ ] `.env` is **not** committed

---

## Option A — Render + Vercel (recommended)

### 1) Backend on Render

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect GitHub repo **Nyaya-Sahayak-BNS-RAG**
3. Set secret:

   | Key | Value |
   |-----|--------|
   | `GOOGLE_API_KEY` | Your Gemini API key |

4. Apply / deploy (first Docker build ~5–15 min).
5. Copy the service URL, e.g. `https://nyaya-sahayak-api.onrender.com`
6. Open `https://YOUR-API.onrender.com/api/health` — expect `"status":"ok"` and `"index_ready":true` (sample corpus is baked into the image).

**Defaults already in `render.yaml`:**
- `GEMINI_MODEL=gemini-2.0-flash-lite` (valid free model)
- `ENABLE_AUTH=false` (uploads work without pasting a key)
- `CORS_ORIGINS=*`
- PDF guards: first ~30 pages / 150 chunks

> Render Free sleeps after ~15 min idle. First wake = **30–90 seconds**.

### 2) Frontend on Vercel

1. [vercel.com/new](https://vercel.com/new) → import the **same** GitHub repo
2. **Root Directory:** leave as repo root (`.`). Do **not** also set it to `frontend` — root `vercel.json` already runs `cd frontend && …`
3. **Environment Variables** (Production **and** Preview):

   | Key | Value |
   |-----|--------|
   | `VITE_API_BASE_URL` | `https://YOUR-API.onrender.com` (no trailing slash) |

4. Deploy.
5. **Important:** turn **off** Vercel Deployment Protection / SSO for this project (or protect only Preview). SSO breaks browser calls if you ever try same-origin `/api`.
6. Open the Vercel URL → Upload panel → **Test connection** → Ask: *What is the punishment for murder under BNS?*

### 3) Optional hardening

| Change | Where |
|--------|--------|
| `CORS_ORIGINS=https://your-app.vercel.app` | Render → Environment → Manual Deploy |
| `ENABLE_AUTH=true` + set `API_KEY` | Render; paste same key in the app’s API key field |

---

## Option B — Railway (all-in-one)

Uses root `Dockerfile` + `railway.toml`.

1. `railway login` → new project from repo  
2. Env: `GOOGLE_API_KEY`, optional `API_KEY`, `CORS_ORIGINS=*`  
3. Deploy → `/api/health`

---

## Option C — Local Docker smoke test

```bash
docker build -f Dockerfile.api -t nyaya-api .
docker run --rm -e GOOGLE_API_KEY=your_key -e ENABLE_AUTH=false -p 10000:10000 nyaya-api
curl http://localhost:10000/api/health
```

---

## Environment reference

| Variable | Required | Notes |
|----------|----------|--------|
| `GOOGLE_API_KEY` | **Yes** | Gemini |
| `GEMINI_MODEL` | No | Default `gemini-2.0-flash-lite` |
| `CORS_ORIGINS` | Prod | `*` or exact Vercel URL |
| `ENABLE_AUTH` / `API_KEY` | No | Off by default for easy first deploy |
| `VITE_API_BASE_URL` | **Yes on Vercel** | Must match live Render URL |
| `MAX_PDF_PAGES` / `MAX_INDEX_CHUNKS` | No | Free-tier RAM guards |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Failed to fetch` / cannot reach API | Open `/api/health`, wait for JSON (cold start), retry. Confirm `VITE_API_BASE_URL`. |
| Gemini model not found | Set `GEMINI_MODEL=gemini-2.0-flash-lite` (not `gemini-3.1-…`). |
| `Invalid or missing X-API-Key` | Set key in UI, or set `ENABLE_AUTH=false` on Render. |
| Upload OOM / timeout on Free | PDF under **15 MB**; only ~30 pages indexed. Prefer sample corpus for demos. |
| Vercel build wrong folder | Root Directory = `.`; do not nest `frontend` twice. |
| Ask works, PDF upload fails | Wake health first; use chunked upload UI; Free tier may OOM on huge Gazettes. |

---

## Security

- Never commit `.env`
- `/api/ask`, `/api/compare`, `/api/section` are public by design
- Upload/ingest/delete respect `ENABLE_AUTH` + `API_KEY` when enabled
