"""Tests for backend.core.ai.groq_client."""

import asyncio
import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.core.ai.groq_client import (  # noqa: E402
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MAX_CHARS,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECS,
    GroqAPIError,
    GroqClient,
    GroqClientConfig,
    load_groq_config,
)


def _clear_groq_env(monkeypatch):
    for name in [
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GROQ_FALLBACK_MODEL",
        "GROQ_TIMEOUT_SECS",
        "AI_EXPLAIN_MAX_CHARS",
    ]:
        monkeypatch.delenv(name, raising=False)


def _make_response(request: httpx.Request, status_code: int, payload):
    return httpx.Response(status_code=status_code, json=payload, request=request)


def _run(coro):
    return asyncio.run(coro)


def test_load_groq_config_defaults(monkeypatch):
    _clear_groq_env(monkeypatch)

    config = load_groq_config()

    assert config.api_key == ""
    assert config.model == DEFAULT_MODEL
    assert config.fallback_model == DEFAULT_FALLBACK_MODEL
    assert config.timeout_secs == DEFAULT_TIMEOUT_SECS
    assert config.max_chars == DEFAULT_MAX_CHARS


def test_load_groq_config_from_env(monkeypatch):
    _clear_groq_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "llama3-70b-8192")
    monkeypatch.setenv("GROQ_FALLBACK_MODEL", "llama3=8b-8192")
    monkeypatch.setenv("GROQ_TIMEOUT_SECS", "30")
    monkeypatch.setenv("AI_EXPLAIN_MAX_CHARS", "9999")

    config = load_groq_config()

    assert config.api_key == "test-key"
    assert config.model == "llama-3.3-70b-versatile"
    assert config.fallback_model == "llama-3.1-8b-instant"
    assert config.timeout_secs == 30.0
    assert config.max_chars == 9999


def test_load_groq_config_rejects_invalid_timeout(monkeypatch):
    _clear_groq_env(monkeypatch)
    monkeypatch.setenv("GROQ_TIMEOUT_SECS", "not-a-number")

    with pytest.raises(GroqAPIError, match="GROQ_TIMEOUT_SECS"):
        load_groq_config()


def test_load_groq_config_rejects_invalid_max_chars(monkeypatch):
    _clear_groq_env(monkeypatch)
    monkeypatch.setenv("AI_EXPLAIN_MAX_CHARS", "0")

    with pytest.raises(GroqAPIError, match="AI_EXPLAIN_MAX_CHARS"):
        load_groq_config()


def test_chat_completion_rejects_missing_key():
    client = GroqClient(config=GroqClientConfig(api_key=""))

    with pytest.raises(GroqAPIError, match="GROQ_API_KEY"):
        _run(client.chat_completion(messages=[{"role": "user", "content": "hi"}]))


def test_chat_completion_retries_on_rate_limit_with_fallback_model():
    seen_models = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        model = body["model"]
        seen_models.append(model)

        if model == "primary-model":
            return _make_response(request, 429, {"error": {"message": "rate limited"}})

        return _make_response(
            request,
            200,
            {
                "model": "fallback-model",
                "choices": [{"message": {"content": "ok"}}],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GroqClient(
        config=GroqClientConfig(
            api_key="test-key",
            model="primary-model",
            fallback_model="fallback-model",
        ),
        http_client=http_client,
    )

    try:
        result = _run(client.chat_completion(messages=[{"role": "user", "content": "ping"}]))
    finally:
        _run(http_client.aclose())

    assert seen_models == ["primary-model", "fallback-model"]
    assert result["model"] == "fallback-model"
    assert result["content"] == "ok"


def test_chat_completion_retries_on_timeout_with_fallback_model():
    seen_models = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        model = body["model"]
        seen_models.append(model)

        if model == "primary-model":
            raise httpx.ReadTimeout("request timed out", request=request)

        return _make_response(
            request,
            200,
            {
                "choices": [{"message": {"content": "fallback ok"}}],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GroqClient(
        config=GroqClientConfig(
            api_key="test-key",
            model="primary-model",
            fallback_model="fallback-model",
        ),
        http_client=http_client,
    )

    try:
        result = _run(client.chat_completion(messages=[{"role": "user", "content": "ping"}]))
    finally:
        _run(http_client.aclose())

    assert seen_models == ["primary-model", "fallback-model"]
    assert result["model"] == "fallback-model"
    assert result["content"] == "fallback ok"


def test_chat_completion_raises_on_invalid_response_format():
    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(request, 200, ["not", "an", "object"])

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GroqClient(
        config=GroqClientConfig(api_key="test-key"),
        http_client=http_client,
    )

    try:
        with pytest.raises(GroqAPIError, match="invalid response format"):
            _run(client.chat_completion(messages=[{"role": "user", "content": "ping"}]))
    finally:
        _run(http_client.aclose())
