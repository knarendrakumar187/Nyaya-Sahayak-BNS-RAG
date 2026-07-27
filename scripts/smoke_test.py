import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read().decode()
            print(f"{method} {path} -> {res.status}")
            print(raw[:2000].encode("ascii", "replace").decode("ascii"))
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"{method} {path} -> HTTP {e.code}")
        print(e.read().decode())
        raise
    except Exception as e:
        print(f"{method} {path} -> ERROR {e}")
        raise


if __name__ == "__main__":
    call("GET", "/api/health")
    call("POST", "/api/compare", {"query": "302"})
    call("POST", "/api/ingest")
    call("GET", "/api/health")
