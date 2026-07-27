"""Security helpers: API key gate, prompt-injection scrubbing."""

from __future__ import annotations

import re

from fastapi import Header, HTTPException

from backend.config import get_settings

_INJECTION = re.compile(
    r"(?is)(?:ignore(?:\s+all)?\s+previous\s+instructions|"
    r"system\s*prompt|you are now|disregard\s+the\s+above|"
    r"<\s*/?\s*script|jailbreak)"
)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if not settings.enable_auth or not settings.api_key:
        return
    if not x_api_key or x_api_key.strip() != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key.")


def scrub_chunk_text(text: str) -> str:
    """Strip common prompt-injection patterns from retrieved chunks."""
    if not text:
        return ""
    cleaned = _INJECTION.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()
