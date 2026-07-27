import json
import urllib.request

health = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=30).read())
print("health:", json.dumps(health, indent=2).encode("ascii", "replace").decode())

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/ask",
    data=json.dumps({"question": "What is the punishment for murder under BNS Section 103?"}).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=180) as res:
    data = json.loads(res.read().decode("utf-8", "replace"))

print("corpus:", data.get("corpus"))
print("answer:", str(data.get("answer", ""))[:500].encode("ascii", "replace").decode())
for i, s in enumerate(data.get("sources", [])[:3], 1):
    print(
        f"source{i}:",
        s.get("source_name"),
        "page",
        s.get("page"),
        "mode",
        s.get("corpus_mode"),
    )
    print(" excerpt:", s.get("excerpt", "")[:120].encode("ascii", "replace").decode())
