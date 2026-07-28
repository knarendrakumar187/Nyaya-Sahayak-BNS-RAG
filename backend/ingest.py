"""
PDF / text → chunks → embeddings → FAISS index.

When PDFs exist in data/raw/, ONLY those PDFs are indexed (demo sample is skipped).
Sample .txt files are a fallback for first-run demos without uploads.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import Settings, get_settings

_INDEX_CACHE: dict = {"key": None, "store": None}


def corpus_version_hash(paths: list[Path]) -> str:
    """Stable short hash of corpus file bytes for citation provenance."""
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.name.lower()):
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        with path.open("rb") as f:
            while True:
                block = f.read(1024 * 1024)
                if not block:
                    break
                h.update(block)
    return h.hexdigest()[:12]


@lru_cache(maxsize=1)
def get_embeddings(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """Lazy-import so importing ingest does not load torch at API boot."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=model_name)


def clear_index_cache() -> None:
    _INDEX_CACHE["key"] = None
    _INDEX_CACHE["store"] = None


def _index_cache_key(settings: Settings) -> tuple:
    faiss_file = settings.index_path / "index.faiss"
    mtime = faiss_file.stat().st_mtime if faiss_file.exists() else 0
    return (str(settings.index_path), mtime, settings.embedding_model)


def load_documents(settings: Settings | None = None) -> tuple[list, dict]:
    """
    Load corpus documents.

    Priority:
    1. If any PDF is in data/raw/ → use ONLY those PDFs (real corpus)
    2. Else fall back to data/sample/*.txt (demo)
    """
    settings = settings or get_settings()
    docs = []

    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.sample_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(settings.raw_dir.glob("*.pdf"))
    mode = "pdf"
    source_files: list[str] = []

    if pdfs:
        pdf_loader = DirectoryLoader(
            str(settings.raw_dir),
            glob="*.pdf",
            loader_cls=PyPDFLoader,
            show_progress=True,
        )
        docs.extend(pdf_loader.load())
        source_files = [p.name for p in pdfs]
        # Cap pages so Render Free (512 MB) can finish indexing
        if settings.max_pdf_pages and len(docs) > settings.max_pdf_pages:
            docs = docs[: settings.max_pdf_pages]
    else:
        mode = "sample"
        txts = sorted(settings.sample_dir.glob("*.txt"))
        if txts:
            txt_loader = DirectoryLoader(
                str(settings.sample_dir),
                glob="*.txt",
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
            )
            docs.extend(txt_loader.load())
            source_files = [p.name for p in txts]

    file_paths = pdfs if pdfs else sorted(settings.sample_dir.glob("*.txt"))
    info = {
        "corpus_mode": mode,  # "pdf" | "sample"
        "source_files": source_files,
        "num_pages_or_files": len(docs),
        "corpus_version": corpus_version_hash(file_paths) if file_paths else None,
        "max_pdf_pages": settings.max_pdf_pages or None,
    }
    return docs, info


def build_index(settings: Settings | None = None) -> dict:
    """Chunk documents, embed them, and persist a FAISS index."""
    import gc

    settings = settings or get_settings()
    # Free old FAISS from memory before a rebuild (important on Render Free 512 MB)
    clear_index_cache()
    gc.collect()

    docs, info = load_documents(settings)
    if not docs:
        raise FileNotFoundError(
            "No documents found. Upload a BNS PDF in the UI (saved to data/raw/) "
            "or keep sample .txt files in data/sample/."
        )

    # Smaller chunks on Free-capped PDF builds = fewer tokens per embed batch
    if info["corpus_mode"] == "sample":
        chunk_size = settings.chunk_size
        chunk_overlap = settings.chunk_overlap
    elif settings.max_index_chunks and settings.max_index_chunks <= 80:
        chunk_size = min(settings.chunk_size, 500)
        chunk_overlap = min(settings.chunk_overlap, 60)
    else:
        chunk_size = max(settings.chunk_size, 800)
        chunk_overlap = max(settings.chunk_overlap, 120)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    if settings.max_index_chunks and len(chunks) > settings.max_index_chunks:
        chunks = chunks[: settings.max_index_chunks]
        info["chunks_capped"] = True
        info["max_index_chunks"] = settings.max_index_chunks
    else:
        info["chunks_capped"] = False

    # Tag every chunk so the UI can show it came from a real PDF vs demo
    for chunk in chunks:
        chunk.metadata["corpus_mode"] = info["corpus_mode"]
        src = chunk.metadata.get("source", "")
        chunk.metadata["source_name"] = Path(str(src)).name if src else "unknown"

    embeddings = get_embeddings(settings.embedding_model)
    batch = max(4, min(settings.embed_batch_size, 16))
    vectorstore = None
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        if vectorstore is None:
            vectorstore = FAISS.from_documents(part, embeddings)
        else:
            vectorstore.add_documents(part)
        gc.collect()

    if vectorstore is None:
        raise RuntimeError("No chunks to index.")

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    if settings.index_path.exists():
        import shutil

        shutil.rmtree(settings.index_path, ignore_errors=True)
    vectorstore.save_local(str(settings.index_path))
    clear_index_cache()
    gc.collect()
    _INDEX_CACHE["key"] = _index_cache_key(settings)
    _INDEX_CACHE["store"] = vectorstore

    meta = {
        "ok": True,
        "num_source_docs": len(docs),
        "num_chunks": len(chunks),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_model": settings.embedding_model,
        "index_path": str(settings.index_path),
        **info,
    }
    (settings.processed_dir / "index_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def load_index(settings: Settings | None = None) -> FAISS:
    """Load FAISS once and reuse in memory (big speedup for Ask)."""
    settings = settings or get_settings()
    if not settings.index_path.exists():
        raise FileNotFoundError(
            "Vector index missing. Upload a PDF or click Rebuild index first."
        )

    key = _index_cache_key(settings)
    if _INDEX_CACHE["store"] is not None and _INDEX_CACHE["key"] == key:
        return _INDEX_CACHE["store"]

    embeddings = get_embeddings(settings.embedding_model)
    store = FAISS.load_local(
        str(settings.index_path),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    _INDEX_CACHE["key"] = key
    _INDEX_CACHE["store"] = store
    return store


def read_index_meta(settings: Settings | None = None) -> dict | None:
    settings = settings or get_settings()
    meta_path = settings.processed_dir / "index_meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    result = build_index()
    print("Index built:", result)
