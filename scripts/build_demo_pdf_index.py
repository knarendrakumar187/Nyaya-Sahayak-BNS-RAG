"""
Build sample FAISS index + pre-baked interview demo PDF index.

Used at Docker image build time so Render Free can "switch to PDF mode"
without running embeddings at runtime (avoids OOM).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from make_demo_pdf import OUT as DEMO_PDF  # noqa: E402
from make_demo_pdf import main as make_pdf  # noqa: E402


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> None:
    from backend.config import get_settings
    from backend.ingest import build_index, clear_index_cache

    make_pdf()
    settings = get_settings()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)

    # --- PDF demo index ---
    for p in settings.raw_dir.glob("*.pdf"):
        p.unlink()
    shutil.copy2(DEMO_PDF, settings.raw_dir / DEMO_PDF.name)
    clear_index_cache()
    pdf_meta = build_index(settings)
    demo_idx = settings.processed_dir / "demo_pdf_index"
    _copytree(settings.index_path, demo_idx)
    (settings.processed_dir / "demo_pdf_meta.json").write_text(
        json.dumps(pdf_meta, indent=2),
        encoding="utf-8",
    )
    print("demo_pdf_index:", pdf_meta)

    # --- Default sample index (no PDFs in raw/) ---
    for p in settings.raw_dir.glob("*.pdf"):
        p.unlink()
    clear_index_cache()
    sample_meta = build_index(settings)
    print("sample_index:", sample_meta)


if __name__ == "__main__":
    main()
