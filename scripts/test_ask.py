import json
import urllib.error
import urllib.request

from backend.config import get_settings

get_settings.cache_clear()
s = get_settings()
key = s.google_api_key or ""
print("provider:", s.llm_provider)
print("model:", s.gemini_model)
print("key_set:", bool(key) and not key.startswith("your_"))

# Rebuild index so new chunk settings apply
ingest_req = urllib.request.Request(
    "http://127.0.0.1:8000/api/ingest",
    data=b"{}",
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(ingest_req, timeout=180) as res:
    print("ingest:", res.read().decode("utf-8", "replace").encode("ascii", "replace").decode())

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/ask",
    data=json.dumps({"question": "What is the punishment for murder under BNS?"}).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=180) as res:
        raw = res.read().decode("utf-8", "replace")
        print("status:", res.status)
        data = json.loads(raw)
        answer = data.get("answer", "")
        print("answer_type:", type(answer).__name__)
        print("answer:", str(answer)[:1200].encode("ascii", "replace").decode())
        print("sources:", len(data.get("sources", [])))
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode("utf-8", "replace").encode("ascii", "replace").decode())
