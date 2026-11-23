"""Tes memakai LLM palsu (mock) sehingga tidak butuh API key / biaya."""
import pytest
from fastapi.testclient import TestClient

from app import llm
from app.schemas import Classification


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def fake_ok(text: str) -> Classification:
    return Classification(
        category="pengiriman", priority="tinggi", sentiment="negatif",
        summary="Pesanan terlambat 3 hari dan pelanggan minta refund.",
        suggested_reply="Mohon maaf atas keterlambatannya, kami cek status pesanan Anda.",
    )


def test_create_and_list(client, monkeypatch):
    monkeypatch.setattr(llm, "classify_ticket", fake_ok)
    r = client.post("/api/tickets", json={"text": "Pesanan saya belum sampai 3 hari!"})
    assert r.status_code == 200
    assert r.json()["category"] == "pengiriman"
    assert len(client.get("/api/tickets").json()) == 1


def test_validation_too_short(client):
    assert client.post("/api/tickets", json={"text": "hi"}).status_code == 422


def test_llm_error_returns_502(client, monkeypatch):
    def boom(_):
        raise RuntimeError("API down")
    monkeypatch.setattr(llm, "classify_ticket", boom)
    assert client.post("/api/tickets", json={"text": "Aplikasi error terus"}).status_code == 502


def test_mock_classifier():
    from app.llm import _mock_classify

    r = _mock_classify("Sudah 3 hari pesanan belum sampai, saya minta refund!")
    assert r.category == "pengiriman"
    assert r.priority in ("tinggi", "kritis")
    assert r.sentiment == "negatif"


def test_health(client):
    assert client.get("/api/health").json()["provider"] in ("mock", "openai_compat", "anthropic")
