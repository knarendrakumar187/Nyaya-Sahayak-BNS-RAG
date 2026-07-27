"""
Expand colloquial legal questions into statute-friendly retrieval queries.

Why: users say "hit-and-run"; BNS text says "rash driving", "negligence", etc.
Pure embedding search on the colloquial phrase often misses the right sections.
"""

from __future__ import annotations

import re

# phrase (regex) -> extra retrieval queries
_EXPANSIONS: list[tuple[re.Pattern[str], list[str]]] = [
    (
        re.compile(r"proxy|impersonat|personation|someone else sits|fake candidate", re.I),
        [
            "cheating by personation Section 319",
            "personation Section 319",
            "whoever cheats by personation",
        ],
    ),
    (
        re.compile(r"bribery|bribe|nepotism|corruption|gratification|paying for selection", re.I),
        [
            "public servant taking gratification Section 171",
            "bribery public servant",
            "gratification other than legal remuneration",
        ],
    ),
    (
        re.compile(r"fake interview|job scam|fake selection|fraudulent panel|extort", re.I),
        [
            "cheating and dishonestly inducing delivery of property Section 318",
            "Section 318 cheating",
            "cheating with knowledge that wrongful loss may ensue",
        ],
    ),
    (
        re.compile(r"merit list|tamper(?:ing)?|interview score|public examination|rank manipulat", re.I),
        [
            "forgery of record of Court or public register",
            "falsification of accounts",
            "forgery for purpose of cheating",
            "public servant framing incorrect document",
        ],
    ),
    (
        re.compile(r"interview|impress|important sections|must[\s-]?know|study", re.I),
        [
            "cheating by personation Section 319",
            "public servant taking gratification Section 171",
            "cheating Section 318",
            "punishment for murder Section 103",
        ],
    ),
    (
        re.compile(r"malpractice|medical negligence|doctor neglig", re.I),
        [
            "causing death by negligence Section 106",
            "rash or negligent act endanger human life",
            "negligent act not amounting to culpable homicide",
        ],
    ),
    (
        re.compile(r"hit[\s-]?and[\s-]?run|flee(?:ing)?\s+(?:the\s+)?scene|left\s+the\s+spot", re.I),
        [
            "rash driving or riding on a public way",
            "causing death by negligence",
            "Section 106 negligence death",
            "Section 281 rash driving",
            "rash or negligent act endanger human life vehicle",
        ],
    ),
    (
        re.compile(r"\bmurder\b|\b302\b", re.I),
        ["punishment for murder Section 103", "whoever commits murder shall be punished"],
    ),
    (
        re.compile(r"\bcheating\b|\b420\b|\bfraud\b", re.I),
        ["cheating Section 318", "dishonestly inducing delivery of property"],
    ),
    (
        re.compile(r"\brape\b|\b376\b", re.I),
        ["punishment for rape Section 64", "sexual offences"],
    ),
    (
        re.compile(r"498\s*a|dowry\s*cruelty|cruelty by husband", re.I),
        ["cruelty by husband or relative of husband Section 85"],
    ),
    (
        re.compile(r"\bsedition\b|124\s*a|sovereignty", re.I),
        ["endangering sovereignty unity integrity Section 152"],
    ),
    (
        re.compile(r"rash\s+driv|negligent\s+driv|road\s+accident", re.I),
        [
            "rash driving or riding on a public way Section 281",
            "causing death by negligence Section 106",
        ],
    ),
]


def expand_queries(question: str) -> list[str]:
    """Return unique retrieval queries: original first, then expansions."""
    q = question.strip()
    out: list[str] = [q] if q else []
    for pattern, extras in _EXPANSIONS:
        if pattern.search(q):
            out.extend(extras)
    # de-dupe, keep order
    seen: set[str] = set()
    unique: list[str] = []
    for item in out:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item.strip())
    return unique


def keyword_terms(question: str) -> list[str]:
    """Terms for a light keyword pass over the docstore."""
    terms = expand_queries(question)
    # also pull quoted section-like tokens
    terms.extend(re.findall(r"\bsection\s+\d+[a-z]?\b", question, flags=re.I))
    terms.extend(re.findall(r"\b\d{2,3}[a-z]?\b", question, flags=re.I))
    # hit-and-run specific legal phrases
    joined = " ".join(terms).lower()
    if "hit" in joined or "rash" in joined or "negligen" in joined:
        terms.extend(
            [
                "rash driving",
                "negligent",
                "public way",
                "causing death by negligence",
                "endanger human life",
            ]
        )
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        key = t.lower().strip()
        if len(key) >= 3 and key not in seen:
            seen.add(key)
            out.append(t.strip())
    return out[:12]
