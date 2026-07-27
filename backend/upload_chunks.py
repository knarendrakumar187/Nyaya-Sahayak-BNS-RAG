"""Chunked PDF upload helpers (Render Free–friendly)."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
UPLOAD_ROOT = Path("/tmp/nyaya_uploads")


def _safe_pdf_name(filename: str | None) -> str:
    raw = Path(filename or "document.pdf").name
    cleaned = SAFE_NAME.sub("_", raw).strip("._")
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned or 'document'}.pdf"
    return cleaned[:180]


def init_upload(filename: str, size_bytes: int) -> dict:
    if size_bytes <= 0 or size_bytes > 40 * 1024 * 1024:
        raise ValueError("PDF size must be between 1 byte and 40 MB.")
    upload_id = str(uuid.uuid4())
    folder = UPLOAD_ROOT / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    meta = folder / "meta.txt"
    meta.write_text(
        f"{_safe_pdf_name(filename)}\n{size_bytes}\n",
        encoding="utf-8",
    )
    return {"upload_id": upload_id, "filename": _safe_pdf_name(filename)}


def save_chunk(upload_id: str, index: int, data: bytes) -> dict:
    if not re.fullmatch(r"[0-9a-f-]{36}", upload_id, flags=re.I):
        raise ValueError("Invalid upload_id.")
    if index < 0 or index > 5000:
        raise ValueError("Invalid chunk index.")
    if not data:
        raise ValueError("Empty chunk.")
    if len(data) > 600_000:
        raise ValueError("Chunk too large.")
    folder = UPLOAD_ROOT / upload_id
    if not folder.exists():
        raise FileNotFoundError("Unknown upload_id. Call /api/upload/init first.")
    (folder / f"{index:06d}.part").write_bytes(data)
    return {"ok": True, "index": index, "bytes": len(data)}


def complete_upload(upload_id: str, dest_dir: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f-]{36}", upload_id, flags=re.I):
        raise ValueError("Invalid upload_id.")
    folder = UPLOAD_ROOT / upload_id
    meta_path = folder / "meta.txt"
    if not meta_path.exists():
        raise FileNotFoundError("Unknown upload_id.")

    filename, size_s, *_ = meta_path.read_text(encoding="utf-8").splitlines() + ["0"]
    expected = int(size_s)
    parts = sorted(folder.glob("*.part"))
    if not parts:
        raise ValueError("No chunks received.")

    data = b"".join(p.read_bytes() for p in parts)
    if len(data) != expected:
        raise ValueError(f"Size mismatch: got {len(data)} bytes, expected {expected}.")
    if not data.startswith(b"%PDF"):
        raise ValueError("Assembled file is not a valid PDF.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)

    shutil.rmtree(folder, ignore_errors=True)
    return {
        "ok": True,
        "filename": dest.name,
        "size_bytes": len(data),
        "path": str(dest),
        "index_rebuilt": False,
    }
