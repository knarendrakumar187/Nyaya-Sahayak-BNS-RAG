"""Create a tiny interview-demo BNS PDF (no extra deps)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample" / "bns_sample_sections.txt"
OUT = ROOT / "data" / "demo" / "BNS_interview_excerpt.pdf"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_content(lines: list[str], start_y: int = 780) -> str:
    parts: list[str] = []
    y = start_y
    for raw in lines:
        line = _escape(raw[:95])
        parts.append(f"BT /F1 9 Tf 48 {y} Td ({line}) Tj ET")
        y -= 12
        if y < 48:
            break
    return "\n".join(parts)


def write_simple_pdf(path: Path, text: str) -> None:
    """Minimal multi-page PDF with Helvetica text (good enough for demo ingest)."""
    all_lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    # ~55 lines per page
    pages: list[list[str]] = []
    for i in range(0, len(all_lines), 55):
        pages.append(all_lines[i : i + 55])
    if not pages:
        pages = [["Nyaya-Sahayak interview demo PDF", "No sample text found."]]
    pages = pages[:4]  # hard cap for Free-tier friendliness

    objects: list[bytes] = []
    # 1: catalog, 2: pages tree, 3: font, then per page: page + content

    def add_obj(body: str) -> int:
        objects.append(body.encode("latin-1", errors="replace"))
        return len(objects)

    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    # placeholder for pages object — fill later
    add_obj("<< /Type /Pages /Kids [] /Count 0 >>")
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_refs: list[int] = []
    for page_lines in pages:
        stream = _page_content(page_lines)
        stream_bytes = stream.encode("latin-1", errors="replace")
        content_id = add_obj(
            f"<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream"
        )
        page_id = add_obj(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        page_refs.append(page_id)

    kids = " ".join(f"{n} 0 R" for n in page_refs)
    objects[1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode("latin-1")
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(f.tell())
            f.write(f"{i} 0 obj\n".encode("latin-1"))
            f.write(obj)
            f.write(b"\nendobj\n")
        xref_pos = f.tell()
        f.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        f.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            f.write(f"{off:010d} 00000 n \n".encode("latin-1"))
        f.write(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
        )


def main() -> None:
    text = SAMPLE.read_text(encoding="utf-8") if SAMPLE.exists() else "BNS demo"
    write_simple_pdf(OUT, text)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
