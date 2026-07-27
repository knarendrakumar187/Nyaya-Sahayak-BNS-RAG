"""Clean Gazette/PDF extraction noise for nicer UI excerpts."""

from __future__ import annotations

import re

_GAZETTE_LINE = re.compile(
    r"(?i)(?:the\s+)?gazette\s+of\s+india(?:\s+extraordinary)?|"
    r"sec\.\s*\d+\]|"
    r"part\s+ii[—\-–].*"
)
_UNDERSCORES = re.compile(r"_{3,}")
_MULTI_SPACE = re.compile(r"\s+")
_BROKEN_SPACES = re.compile(r"(?<=\w)\s+(?=\w)")


def clean_excerpt(text: str, limit: int = 220) -> str:
    if not text:
        return ""
    lines = []
    for raw in text.replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if _UNDERSCORES.fullmatch(line.replace(" ", "")):
            continue
        if _GAZETTE_LINE.search(line) and len(line) < 120:
            continue
        line = _UNDERSCORES.sub(" ", line)
        line = _GAZETTE_LINE.sub(" ", line)
        lines.append(line)

    joined = " ".join(lines)
    joined = joined.replace("—", "-").replace("–", "-")
    joined = _MULTI_SPACE.sub(" ", joined).strip(" -|_")
    if len(joined) > limit:
        joined = joined[: limit - 1].rsplit(" ", 1)[0] + "…"
    return joined
