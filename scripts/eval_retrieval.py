"""
Simple retrieval evaluation for interview demos.

Run from project root (with index already built):
  .venv\\Scripts\\python scripts\\eval_retrieval.py

What this proves in interviews:
- You can measure whether the RIGHT chunk is retrieved (before the LLM speaks)
- RAG quality starts with retrieval, not just a fancy prompt
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.rag import retrieve_with_scores

# Expected substring that should appear in a top retrieved chunk
CASES = [
    {
        "question": "What is the punishment for murder under BNS?",
        "must_include": "Section 103",
    },
    {
        "question": "Punishment for cheating under the new law",
        "must_include": "318",
    },
    {
        "question": "What is cruelty by husband under BNS?",
        "must_include": "Section 85",
    },
    {
        "question": "rash driving on a public way",
        "must_include": "281",
    },
]


def main() -> int:
    settings = get_settings()
    if not settings.index_path.exists():
        print("Index missing. Build it first: POST /api/ingest or use the Upload UI.")
        return 1

    passed = 0
    print("Nyaya-Sahayak retrieval eval")
    print(f"top_k={settings.top_k}  embeddings={settings.embedding_model}\n")

    for case in CASES:
        ranked = retrieve_with_scores(case["question"], settings)
        haystack = "\n".join(doc.page_content for doc, _ in ranked)
        ok = case["must_include"].lower() in haystack.lower()
        passed += int(ok)
        best = ranked[0][1] if ranked else None
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['question']}")
        print(f"       expect containing: {case['must_include']!r}")
        print(f"       best_l2={best:.4f}" if best is not None else "       no hits")
        if ranked:
            preview = ranked[0][0].page_content.replace("\n", " ")[:110]
            print(f"       top_chunk: {preview}...")
        print()

    total = len(CASES)
    print(f"Score: {passed}/{total} ({100 * passed / total:.0f}%)")
    print("Tip: If FAIL, tune chunk_size/top_k or improve the corpus — not the LLM prompt first.")
    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
