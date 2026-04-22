"""Tests for POST /ai-explain endpoint behavior."""

import os
import sys

import httpx
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def _valid_request_payload():
    return {
        "finding": {
            "function": "demo",
            "readable_name": "demo",
            "category": "signed_overflow",
            "severity": "critical",
            "confidence": "HIGH",
            "detail": "Signed overflow assumptions changed control flow.",
            "fix": "Use checked arithmetic.",
            "metrics": {
                "blocks_O0": 4,
                "blocks_O2": 1,
                "branches_O0": 2,
                "branches_O2": 0,
            },
            "ir": {
                "O0": "define i32 @demo(i32 %x) {\nentry:\n  %cmp = icmp sgt i32 %x, 0\n  br i1 %cmp, label %a, label %b\n}\n",
                "O2": "define i32 @demo(i32 %x) {\nentry:\n  ret i32 1\n}\n",
            },
        },
        "source_snippet": "int demo(int x) { return x + 1 > x; }",
    }


def test_ai_explain_status_reports_disabled_without_key(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    response = client.get("/ai-explain/status")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert "GROQ_API_KEY" in body["reason"]


def test_ai_explain_status_reports_enabled_with_key(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "llama3-70b-8192")

    response = client.get("/ai-explain/status")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["reason"] == ""


def test_ai_explain_returns_503_when_key_missing(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    response = client.post("/ai-explain", json=_valid_request_payload())

    assert response.status_code == 503
    assert "AI not configured" in response.json()["detail"]


def test_ai_explain_rejects_oversized_payload(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("AI_EXPLAIN_MAX_CHARS", "100")

    payload = _valid_request_payload()
    payload["source_snippet"] = "x" * 60_000

    response = client.post("/ai-explain", json=payload)

    assert response.status_code == 400
    assert "payload exceeds size limit" in response.json()["detail"]


def test_ai_explain_returns_structured_response(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async def fake_chat_completion(self, messages, **kwargs):  # noqa: ANN001
        return {
            "model": "llama-3.3-70b-versatile",
            "content": (
                '{"summary_plain":"summary","what_is_the_ub":"ub","what_changed_in_ir":"ir",'
                '"why_optimizer_removed_code":"why","fixes":["fix1"],"safer_rewrite":"rewrite","caveats":"none"}'
            ),
        }

    monkeypatch.setattr("backend.main.GroqClient.chat_completion", fake_chat_completion)

    response = client.post("/ai-explain", json=_valid_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["explanation"]["summary_plain"] == "summary"
    assert body["explanation"]["fixes"] == ["fix1"]


def test_ai_explain_propagates_rate_limit_error(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    from backend.core.ai import GroqAPIError

    async def fake_chat_completion(self, messages, **kwargs):  # noqa: ANN001
        raise GroqAPIError("Groq rate limit reached: retry later", status_code=429)

    monkeypatch.setattr("backend.main.GroqClient.chat_completion", fake_chat_completion)

    response = client.post("/ai-explain", json=_valid_request_payload())

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_ai_explain_returns_200_with_mocked_httpx_response(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async def fake_post(self, url, *args, **kwargs):  # noqa: ANN001
        content = (
            '{"summary_plain":"from-httpx","what_is_the_ub":"ub",'
            '"what_changed_in_ir":"ir","why_optimizer_removed_code":"why",'
            '"fixes":["fix-httpx"],"safer_rewrite":"rewrite","caveats":"none"}'
        )
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama-3.3-70b-versatile",
                "choices": [{"message": {"content": content}}],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("backend.core.ai.groq_client.httpx.AsyncClient.post", fake_post)

    response = client.post("/ai-explain", json=_valid_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["explanation"]["summary_plain"] == "from-httpx"
    assert body["explanation"]["fixes"] == ["fix-httpx"]
