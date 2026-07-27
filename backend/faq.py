"""
Fast FAQ answers for common interview-malpractice demos.

These chips are answered from curated grounded notes + quick section lookup,
so demos stay fast (no multi-query embedding storm).
"""

from __future__ import annotations

import re

FAQS: list[dict] = [
    {
        "id": "proxy",
        "patterns": [
            re.compile(r"proxy|impersonat|personation|someone else sits", re.I),
        ],
        "sections": ["319"],
        "answer": """**Answer:** If a proxy candidate sits in an interview for someone else, **BNS Section 319 (Cheating by personation)** is the key provision.

**Relevant section(s):**
- **BNS Section 319** — Cheating by personation

**What it covers:**
- A proxy appearing in an interview/exam on behalf of the real applicant

**Punishment / notes:**
- Imprisonment up to **3 years**, or fine, or both (as provided in BNS for this offence)
- Always verify exact wording in the official BNS text for the case facts

**Disclaimer:** Educational information only, not legal advice.
""",
    },
    {
        "id": "bribery",
        "patterns": [
            re.compile(r"bribery|bribe|nepotism|corruption|gratification|paying for selection", re.I),
        ],
        "sections": ["171"],
        "answer": """**Answer:** Illegal favour or bribes in selection can attract **BNS provisions on public-servant gratification**, and for government interviews also the **Prevention of Corruption Act, 1988**.

**Relevant section(s):**
- **BNS Section 171** family provisions on public servant taking gratification (check exact clause in your PDF)
- **Prevention of Corruption Act, 1988 (Section 7)** may apply alongside BNS for government recruitment

**What it covers:**
- Interviewer/official taking a bribe or illegally favouring a candidate

**Punishment / notes:**
- Corruption cases can involve imprisonment of about **3 to 7 years** plus fine under the PC Act framework (confirm current statutory text)
- Use official Acts for exact punishment wording

**Disclaimer:** Educational information only, not legal advice.
""",
    },
    {
        "id": "scam",
        "patterns": [
            re.compile(r"fake interview|job scam|fake selection|fraudulent panel|cheat(?:ing)? candidates", re.I),
        ],
        "sections": ["318"],
        "answer": """**Answer:** Fake interviews or job scams that extract money from candidates are typically covered by **BNS Section 318 (cheating)**, especially aggravated cheating clauses.

**Relevant section(s):**
- **BNS Section 318** — Cheating / dishonestly inducing delivery of property (classic replacement area for old IPC 420 concepts)

**What it covers:**
- Fake interview calls, fake selection letters, fraudulent panels used to extort money

**Punishment / notes:**
- Depending on the exact clause and facts, punishment can extend up to **7 years** with fine
- Confirm the precise sub-section in the official BNS PDF for your facts

**Disclaimer:** Educational information only, not legal advice.
""",
    },
    {
        "id": "tamper",
        "patterns": [
            re.compile(r"merit list|tamper(?:ing)?|interview score|public examination|rank", re.I),
        ],
        "sections": ["336", "337", "340"],
        "answer": """**Answer:** Manipulating merit lists or interview scores in public exams is mainly addressed by the **Public Examinations (Prevention of Unfair Means) Act, 2024**, with related BNS forgery/falsification provisions also potentially relevant.

**Relevant law:**
- **Public Examinations Act, 2024 (Section 3)** — tampering with documents/merit/ranks in public examinations (UPSC, SSC, banking, state boards, etc.)
- Related BNS forgery / incorrect-document offences may also apply depending on facts

**Punishment / notes (Public Examinations Act):**
- Generally **3 to 5 years** imprisonment and fine up to **₹10 lakh**
- For organised / institutional cases, higher ranges (about **5 to 10 years**) and very heavy fines can apply
- This Act is separate from BNS — upload that PDF too if you want page citations from it

**Disclaimer:** Educational information only, not legal advice.
""",
    },
]


def match_faq(question: str) -> dict | None:
    q = (question or "").strip()
    if not q:
        return None
    # Normalize fancy punctuation from UI chips
    normalized = (
        q.replace("—", "-")
        .replace("–", "-")
        .replace("/", " ")
        .lower()
    )
    for item in FAQS:
        if any(p.search(q) or p.search(normalized) for p in item["patterns"]):
            return item
    # Explicit chip fallbacks
    chip_map = {
        "proxy": "proxy",
        "impersonation": "proxy",
        "bribery": "bribery",
        "corruption": "bribery",
        "fake job": "scam",
        "scam": "scam",
        "merit list": "tamper",
        "tampering": "tamper",
    }
    for needle, faq_id in chip_map.items():
        if needle in normalized:
            for item in FAQS:
                if item["id"] == faq_id:
                    return item
    return None
