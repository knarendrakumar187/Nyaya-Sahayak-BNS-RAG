"""
IPC ↔ BNS compare feature (the resume X-factor).

Uses a curated JSON mapping table. Optionally asks the LLM to explain
the mapping in plain language when an API key is available.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import Settings, get_settings
from backend.prompts import COMPARE_PROMPT


@lru_cache
def load_mappings(path: str | None = None) -> list[dict]:
    settings = get_settings()
    mapping_path = path or str(settings.mappings_path)
    data = json.loads(open(mapping_path, encoding="utf-8").read())
    return data["mappings"]


def _extract_section_number(query: str) -> str | None:
    match = re.search(r"(?:section|sec\.?|§)\s*(\d+[A-Za-z]?)", query, re.I)
    if match:
        return match.group(1).upper()
    # bare number like "302" or "498A"
    match = re.search(r"\b(\d{2,3}[A-Za-z]?)\b", query)
    if match:
        return match.group(1).upper()
    return None


def find_mappings(query: str) -> list[dict]:
    mappings = load_mappings()
    q = query.lower().strip()
    section = _extract_section_number(query)

    hits: list[dict] = []
    for row in mappings:
        ipc = str(row.get("ipc_section", "")).upper()
        bns = str(row.get("bns_section", "")).upper()
        title = str(row.get("title", "")).lower()
        keywords = " ".join(row.get("keywords", [])).lower()

        if section and (section == ipc or section == bns):
            hits.append(row)
            continue
        if q and (q in title or q in keywords or q in ipc.lower() or q in bns.lower()):
            hits.append(row)

    # de-dupe while preserving order
    seen = set()
    unique = []
    for row in hits:
        key = (row.get("ipc_section"), row.get("bns_section"))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def compare(query: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    hits = find_mappings(query)

    explanation = None
    if hits:
        try:
            from backend.rag import get_llm

            llm = get_llm(settings)
            messages = [
                SystemMessage(
                    content="You explain Indian criminal law IPC→BNS mappings briefly and accurately."
                ),
                HumanMessage(
                    content=COMPARE_PROMPT.format(
                        mapping_json=json.dumps(hits, indent=2),
                        query=query,
                    )
                ),
            ]
            from backend.rag import _as_text

            explanation = _as_text(llm.invoke(messages).content)
        except Exception:
            # Mapping table still useful without an LLM key
            explanation = None

    if not hits:
        return {
            "query": query,
            "mappings": [],
            "explanation": (
                "No IPC↔BNS mapping found for that query in the curated table. "
                "Try a section number (e.g. 302) or offence name (e.g. murder, cheating)."
            ),
        }

    if explanation is None:
        lines = []
        for row in hits:
            lines.append(
                f"IPC Section {row['ipc_section']} → BNS Section {row['bns_section']} "
                f"({row['title']}). {row.get('notes', '')}"
            )
        explanation = "\n".join(lines)

    return {"query": query, "mappings": hits, "explanation": explanation}
