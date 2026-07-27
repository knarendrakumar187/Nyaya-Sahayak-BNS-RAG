"""
Nyaya-Sahayak API

Local:
  uvicorn backend.main:app --reload --port 8000

Production (serves API + built React UI when frontend/dist exists):
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.compare import compare
from backend.config import get_settings
from backend.eval_api import run_eval
from backend.ingest import build_index, load_index, read_index_meta
from backend.jobs import get_job, start_ingest_job
from backend.logging_mw import RequestIdMiddleware, logger
from backend.rag import ask, ask_stream
from backend.sections import find_section
from backend.security import require_api_key

MAX_UPLOAD_BYTES = 40 * 1024 * 1024  # 40 MB
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
APP_VERSION = "1.2.0"

limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Bind the HTTP port first; warm FAISS/embeddings in the background."""
    import threading

    settings = get_settings()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)

    def _warm() -> None:
        try:
            if settings.index_path.exists():
                load_index(settings)
                logger.info("FAISS index warmed")
            else:
                logger.info("No FAISS index yet — user must Rebuild index")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Index warm skipped: %s", exc)

    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(
    title="Nyaya-Sahayak",
    description="RAG bot for Bharatiya Nyaya Sanhita (BNS) and IPC↔BNS comparison",
    version=APP_VERSION,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_boot = get_settings()
_cors = [o.strip() for o in _boot.cors_origins.split(",") if o.strip()]
_allow_all = _cors == ["*"]
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else _cors,
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DEFAULT_LIMIT = _boot.rate_limit or "30/minute"


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    language: str = Field(default="en", max_length=8)
    history: list[ChatTurn] = Field(default_factory=list)
    hybrid: bool = True


class CompareRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class SectionRequest(BaseModel):
    section: str = Field(..., min_length=1, max_length=20)


@app.get("/api/health")
def health():
    """Liveness + index status (no rate limit — used by deploy platforms)."""
    settings = get_settings()
    meta = read_index_meta(settings) or {}
    return {
        "status": "ok",
        "index_ready": settings.index_path.exists(),
        "llm_provider": settings.llm_provider,
        "gemini_model": settings.gemini_model,
        "app": "Nyaya-Sahayak",
        "version": APP_VERSION,
        "corpus_mode": meta.get("corpus_mode"),
        "source_files": meta.get("source_files", []),
        "num_chunks": meta.get("num_chunks"),
        "corpus_version": meta.get("corpus_version"),
        "auth_required": bool(settings.enable_auth and settings.api_key),
        "frontend_bundled": (
            settings.serve_frontend and (settings.frontend_dist / "index.html").exists()
        ),
    }


@app.post("/api/ingest")
@limiter.limit("10/minute")
def ingest(request: Request, _: None = Depends(require_api_key)):
    settings = get_settings()
    try:
        meta = build_index(settings)
        return {"ok": True, **meta}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc


@app.post("/api/ingest/async")
@limiter.limit("10/minute")
def ingest_async(request: Request, _: None = Depends(require_api_key)):
    job_id = start_ingest_job()
    return {"ok": True, "job_id": job_id}


@app.get("/api/ingest/status/{job_id}")
@limiter.limit(_DEFAULT_LIMIT)
def ingest_status(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown ingest job.")
    return job


def _safe_pdf_name(filename: str | None) -> str:
    raw = Path(filename or "document.pdf").name
    cleaned = SAFE_NAME.sub("_", raw).strip("._")
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned or 'document'}.pdf"
    return cleaned[:180]


@app.get("/api/documents")
@limiter.limit(_DEFAULT_LIMIT)
def list_documents(request: Request):
    settings = get_settings()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(settings.raw_dir.glob("*.pdf"))
    return {
        "documents": [
            {"name": f.name, "size_bytes": f.stat().st_size}
            for f in files
        ]
    }


@app.delete("/api/documents/{name}")
@limiter.limit("20/minute")
def delete_document(request: Request, name: str, _: None = Depends(require_api_key)):
    settings = get_settings()
    safe = Path(name).name
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.pdf", safe, flags=re.I):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    target = settings.raw_dir / safe
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="PDF not found.")
    target.unlink()
    return {"ok": True, "deleted": safe}


@app.post("/api/upload")
@limiter.limit("10/minute")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    rebuild_index: bool = True,
    _: None = Depends(require_api_key),
):
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Invalid content type. Upload a PDF.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="PDF too large (max 40 MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File does not look like a valid PDF.")

    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.raw_dir / _safe_pdf_name(file.filename)
    dest.write_bytes(data)

    result: dict = {
        "ok": True,
        "filename": dest.name,
        "size_bytes": len(data),
        "path": str(dest),
        "index_rebuilt": False,
    }

    if rebuild_index:
        try:
            meta = build_index(settings)
            result["index_rebuilt"] = True
            result["ingest"] = meta
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"PDF saved as {dest.name}, but index rebuild failed: {exc}",
            ) from exc

    return result


@app.post("/api/ask")
@limiter.limit(_DEFAULT_LIMIT)
def ask_question(request: Request, body: AskRequest):
    settings = get_settings()
    try:
        history = [t.model_dump() for t in body.history]
        return ask(
            body.question,
            settings,
            language=body.language,
            history=history,
            hybrid=body.hybrid,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ask failed: {exc}") from exc


@app.post("/api/ask/stream")
@limiter.limit(_DEFAULT_LIMIT)
def ask_question_stream(request: Request, body: AskRequest):
    settings = get_settings()
    history = [t.model_dump() for t in body.history]

    def event_gen():
        try:
            for item in ask_stream(
                body.question,
                settings,
                language=body.language,
                history=history,
                hybrid=body.hybrid,
            ):
                payload = json.dumps(item["data"], ensure_ascii=False)
                yield f"event: {item['event']}\ndata: {payload}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = json.dumps({"detail": str(exc)})
            yield f"event: error\ndata: {err}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/compare")
@limiter.limit(_DEFAULT_LIMIT)
def compare_laws(request: Request, body: CompareRequest):
    settings = get_settings()
    try:
        return compare(body.query, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compare failed: {exc}") from exc


@app.post("/api/section")
@limiter.limit(_DEFAULT_LIMIT)
def section_lookup(request: Request, body: SectionRequest):
    settings = get_settings()
    try:
        return find_section(body.section, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Section lookup failed: {exc}") from exc


@app.get("/api/eval")
@limiter.limit("5/minute")
def eval_retrieval(request: Request):
    try:
        return run_eval()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eval failed: {exc}") from exc


def _mount_frontend() -> None:
    settings = get_settings()
    dist = settings.frontend_dist
    if not settings.serve_frontend or not (dist / "index.html").exists():
        return

    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    def spa_root():
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        first = full_path.split("/", 1)[0]
        if first in {"api", "docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


_mount_frontend()
