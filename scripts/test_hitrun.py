import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/ask",
    data=json.dumps(
        {"question": "Hit-and-run: which BNS sections apply?"}
    ).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=180) as res:
    data = json.loads(res.read().decode("utf-8", "replace"))

print("low_confidence:", data.get("retrieval", {}).get("low_confidence"))
print("best_l2:", data.get("retrieval", {}).get("best_l2_distance"))
print("queries:", data.get("retrieval", {}).get("queries_used"))
print("answer:", str(data.get("answer", ""))[:900].encode("ascii", "replace").decode())
print("---sources---")
for s in data.get("sources", []):
    print(
        s.get("source_name"),
        "p.",
        (s.get("page") or 0) + 1 if s.get("page") is not None else "?",
        s.get("relevance"),
        s.get("l2_distance"),
    )
    print(" ", s.get("excerpt", "")[:140].encode("ascii", "replace").decode())
