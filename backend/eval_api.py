"""Retrieval evaluation for interview demos / production quality checks."""

from __future__ import annotations

from backend.config import get_settings
from backend.rag import retrieve_with_scores

CASES = [
    {
        "question": "What is the punishment for murder under BNS?",
        "must_include": "103",
    },
    {
        "question": "Punishment for cheating under the new law",
        "must_include": "318",
    },
    {
        "question": "rash driving on a public way",
        "must_include": "281",
    },
    {
        "question": "Proxy interview impersonation section",
        "must_include": "319",
    },
    {
        "question": "causing death by negligence",
        "must_include": "106",
    },
]


def run_eval() -> dict:
    settings = get_settings()
    if not settings.index_path.exists():
        raise FileNotFoundError("Index missing. Build it before running eval.")

    results = []
    passed = 0
    for case in CASES:
        ranked, _, _ = retrieve_with_scores(case["question"], settings, top_k=8)
        haystack = "\n".join(doc.page_content for doc, _ in ranked)
        ok = case["must_include"].lower() in haystack.lower()
        passed += int(ok)
        best = float(ranked[0][1]) if ranked else None
        results.append(
            {
                "question": case["question"],
                "expect": case["must_include"],
                "pass": ok,
                "best_l2": round(best, 4) if best is not None else None,
                "top_excerpt": (ranked[0][0].page_content[:140] if ranked else ""),
            }
        )

    total = len(CASES)
    return {
        "passed": passed,
        "total": total,
        "score_pct": round(100 * passed / total, 1) if total else 0,
        "metric": "retrieval_hit_at_k (substring in top chunks)",
        "cases": results,
    }
