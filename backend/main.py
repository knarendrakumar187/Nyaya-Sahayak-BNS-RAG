"""
Nyaya-Sahayak API

Run from project root:
  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.compare import compare
from backend.config import get_settings
from backend.ingest import build_index, read_index_meta
from backend.rag import ask
from backend.sections import find_section

MAX_UPLOAD_BYTES = 40 * 1024 * 1024  # 40 MB
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

app = FastAPI(
    title="Nyaya-Sahayak",
    description="RAG bot for Bharatiya Nyaya Sanhita (BNS) and IPC↔BNS comparison",
    version="1.0.0",
)

_boot = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _boot.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class CompareRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class SectionRequest(BaseModel):
    section: str = Field(..., min_length=1, max_length=20)


@app.get("/api/health")
def health():
    settings = get_settings()
    meta = read_index_meta(settings) or {}
    return {
        "status": "ok",
        "index_ready": settings.index_path.exists(),
        "llm_provider": settings.llm_provider,
        "gemini_model": settings.gemini_model,
        "app": "Nyaya-Sahayak",
        "corpus_mode": meta.get("corpus_mode"),
        "source_files": meta.get("source_files", []),
        "num_chunks": meta.get("num_chunks"),
    }


@app.post("/api/ingest")
def ingest():
    """Build / rebuild the FAISS index from data/raw PDFs + data/sample texts."""
    settings = get_settings()
    try:
        meta = build_index(settings)
        return {"ok": True, **meta}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc


def _safe_pdf_name(filename: str | None) -> str:
    raw = Path(filename or "document.pdf").name
    cleaned = SAFE_NAME.sub("_", raw).strip("._")
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned or 'document'}.pdf"
    return cleaned[:180]


@app.get("/api/documents")
def list_documents():
    """List PDFs currently in data/raw/."""
    settings = get_settings()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(settings.raw_dir.glob("*.pdf"))
    return {
        "documents": [
            {
                "name": f.name,
                "size_bytes": f.stat().st_size,
            }
            for f in files
        ]
    }


@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    rebuild_index: bool = True,
):
    """Upload a BNS/IPC PDF into data/raw/ and optionally rebuild FAISS."""
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
def ask_question(body: AskRequest):
    settings = get_settings()
    try:
        return ask(body.question, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ask failed: {exc}") from exc


@app.post("/api/compare")
def compare_laws(body: CompareRequest):
    settings = get_settings()
    try:
        return compare(body.query, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compare failed: {exc}") from exc


@app.post("/api/section")
def section_lookup(body: SectionRequest):
    """Lexical lookup for a BNS section number inside the indexed PDF chunks."""
    settings = get_settings()
    try:
        return find_section(body.section, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Section lookup failed: {exc}") from exc
