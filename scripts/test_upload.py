"""Smoke-test PDF upload without printing secrets."""

import json
import urllib.request
from pathlib import Path

# Minimal valid-enough PDF header + body for our %PDF check and storage
pdf_bytes = b"""%PDF-1.4
1 0 obj<<>>endobj
trailer<<>>
%%EOF
"""

path = Path(__file__).resolve().parent / "_tiny_test.pdf"
path.write_bytes(pdf_bytes)

boundary = "----NyayaBoundary7MA4YWxkTrZu0gW"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="tiny_test.pdf"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/upload?rebuild_index=false",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)

with urllib.request.urlopen(req, timeout=60) as res:
    raw = res.read().decode("utf-8", "replace")
    print(raw.encode("ascii", "replace").decode())

docs = urllib.request.urlopen("http://127.0.0.1:8000/api/documents", timeout=30).read()
print(docs.decode("utf-8", "replace").encode("ascii", "replace").decode())

path.unlink(missing_ok=True)
