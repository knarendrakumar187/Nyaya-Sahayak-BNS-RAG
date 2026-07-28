"""Interview demo corpus helpers (pre-baked PDF index for Render Free)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from backend.config import Settings, get_settings
from backend.ingest import clear_index_cache


DEMO_PDF_NAME = "BNS_interview_excerpt.pdf"


def demo_pdf_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / "demo" / DEMO_PDF_NAME


def demo_index_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.processed_dir / "demo_pdf_index"


def demo_meta_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.processed_dir / "demo_pdf_meta.json"


def activate_interview_demo_pdf(settings: Settings | None = None) -> dict:
    """
    Switch live corpus to the bundled interview PDF using a pre-built FAISS index.
    No runtime embedding — safe on Render Free 512 MB.
    """
    settings = settings or get_settings()
    pdf = demo_pdf_path(settings)
    idx = demo_index_dir(settings)
    meta_file = demo_meta_path(settings)

    if not pdf.exists():
        raise FileNotFoundError(
            f"Demo PDF missing at {pdf}. Rebuild the Docker image (scripts/build_demo_pdf_index.py)."
        )
    if not idx.exists() or not (idx / "index.faiss").exists():
        # Local fallback: live build (has more RAM than Render Free)
        from backend.ingest import build_index

        settings.raw_dir.mkdir(parents=True, exist_ok=True)
        for p in settings.raw_dir.glob("*.pdf"):
            p.unlink()
        shutil.copy2(pdf, settings.raw_dir / pdf.name)
        clear_index_cache()
        return build_index(settings)

    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    for p in settings.raw_dir.glob("*.pdf"):
        p.unlink()
    shutil.copy2(pdf, settings.raw_dir / pdf.name)

    clear_index_cache()
    if settings.index_path.exists():
        shutil.rmtree(settings.index_path)
    shutil.copytree(idx, settings.index_path)

    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        (settings.processed_dir / "index_meta.json").write_text(
            json.dumps(meta, indent=2),
            encoding="utf-8",
        )
    else:
        meta = {
            "ok": True,
            "corpus_mode": "pdf",
            "source_files": [pdf.name],
            "num_chunks": None,
        }
        (settings.processed_dir / "index_meta.json").write_text(
            json.dumps(meta, indent=2),
            encoding="utf-8",
        )

    meta["ok"] = True
    meta["demo"] = True
    meta["note"] = "Interview demo PDF activated (pre-built index, no live embedding)."
    return meta
