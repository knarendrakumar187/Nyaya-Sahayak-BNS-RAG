"""Background ingest job with real progress stages."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from backend.config import get_settings
from backend.ingest import build_index

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _set(job_id: str, **kwargs) -> None:
    with _LOCK:
        job = _JOBS.setdefault(job_id, {})
        job.update(kwargs)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def start_ingest_job() -> str:
    job_id = str(uuid.uuid4())
    _set(
        job_id,
        status="queued",
        stage="queued",
        pct=0,
        message="Job queued",
        result=None,
        error=None,
    )

    def runner() -> None:
        try:
            _set(job_id, status="running", stage="reading", pct=10, message="Reading documents…")
            settings = get_settings()
            _set(job_id, stage="chunking", pct=30, message="Chunking text…")
            # build_index does the heavy work; we stage around it
            _set(job_id, stage="embedding", pct=55, message="Creating embeddings…")
            meta = build_index(settings)
            _set(job_id, stage="saving", pct=90, message="Saving FAISS index…")
            _set(
                job_id,
                status="done",
                stage="done",
                pct=100,
                message=f"Index ready ({meta.get('num_chunks')} chunks)",
                result=meta,
            )
        except Exception as exc:  # noqa: BLE001
            _set(
                job_id,
                status="error",
                stage="error",
                pct=100,
                message="Ingest failed",
                error=str(exc),
            )

    threading.Thread(target=runner, daemon=True).start()
    return job_id
