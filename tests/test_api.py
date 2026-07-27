"""Minimal pytest smoke tests for Nyaya-Sahayak API."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "index_ready" in data


def test_documents_list():
    res = client.get("/api/documents")
    assert res.status_code == 200
    assert "documents" in res.json()


def test_ask_validation():
    res = client.post("/api/ask", json={"question": "hi"})
    assert res.status_code == 422
