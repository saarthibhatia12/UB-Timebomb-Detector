"""Groq API client wrapper used by the AI explanation endpoint."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

import httpx


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_FALLBACK_MODEL = "llama-3.1-8b-instant"
DEFAULT_TIMEOUT_SECS = 25.0
DEFAULT_MAX_CHARS = 12_000

MODEL_ALIASES = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "llama3=8b-8192": "llama-3.1-8b-instant",
}


class GroqAPIError(RuntimeError):
    """Raised when the Groq API is unavailable or returns an invalid response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GroqClientConfig:
    """Configuration for Groq API access."""

    api_key: str = ""
    model: str = DEFAULT_MODEL
    fallback_model: str = DEFAULT_FALLBACK_MODEL
    timeout_secs: float = DEFAULT_TIMEOUT_SECS
    max_chars: int = DEFAULT_MAX_CHARS
    api_url: str = GROQ_API_URL

    @property
    def enabled(self) -> bool:
        """Whether AI explain is configured with an API key."""
        return bool(self.api_key)


def _read_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise GroqAPIError(f"{name} must be a number") from exc
    if value <= 0:
        raise GroqAPIError(f"{name} must be greater than zero")
    return value


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise GroqAPIError(f"{name} must be an integer") from exc
    if value <= 0:
        raise GroqAPIError(f"{name} must be greater than zero")
    return value


def _normalize_model_name(raw_value: str | None) -> str:
    """Normalize common typos and casing for Groq model IDs."""

    if raw_value is None:
        return ""
    return raw_value.strip().lower().replace("=", "-")


def _resolve_model_name(raw_value: str | None, default: str) -> str:
    normalized = _normalize_model_name(raw_value)
    if not normalized:
        return default
    return MODEL_ALIASES.get(normalized, normalized)


def load_groq_config() -> GroqClientConfig:
    """Load Groq configuration from environment variables."""

    return GroqClientConfig(
        api_key=os.getenv("GROQ_API_KEY", "").strip(),
        model=_resolve_model_name(os.getenv("GROQ_MODEL"), DEFAULT_MODEL),
        fallback_model=_resolve_model_name(os.getenv("GROQ_FALLBACK_MODEL"), DEFAULT_FALLBACK_MODEL),
        timeout_secs=_read_float_env("GROQ_TIMEOUT_SECS", DEFAULT_TIMEOUT_SECS),
        max_chars=_read_int_env("AI_EXPLAIN_MAX_CHARS", DEFAULT_MAX_CHARS),
    )


class GroqClient:
    """Small async client for Groq's OpenAI-compatible chat completions API."""

    def __init__(
        self,
        config: GroqClientConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or load_groq_config()
        self._http_client = http_client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Send a chat completion request to Groq with one fallback retry."""

        self._ensure_configured()

        retryable_error: GroqAPIError | None = None

        for index, model_name in enumerate(self._candidate_models()):
            try:
                return await self._request_completion(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            except GroqAPIError as exc:
                if self._should_retry(exc) and index == 0:
                    retryable_error = exc
                    continue
                raise

        if retryable_error is not None:
            raise retryable_error
        raise GroqAPIError("Groq request failed before it could be sent")

    def _ensure_configured(self) -> None:
        if not self.config.enabled:
            raise GroqAPIError("Groq API key is missing. Set GROQ_API_KEY to enable AI explanations.")

    def _candidate_models(self) -> List[str]:
        models = [self.config.model]
        if self.config.fallback_model and self.config.fallback_model != self.config.model:
            models.append(self.config.fallback_model)
        return models

    def _should_retry(self, exc: GroqAPIError) -> bool:
        return exc.status_code == 429 or "timed out" in str(exc).lower()

    async def _request_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.config.timeout_secs)

        if self._http_client is not None:
            response = await self._send_request(
                self._http_client,
                payload=payload,
                headers=headers,
                timeout=timeout,
            )
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await self._send_request(
                    client,
                    payload=payload,
                    headers=headers,
                    timeout=timeout,
                )

        data = self._parse_response(response)
        if not data.get("model"):
            data["model"] = model
        return data

    async def _send_request(
        self,
        client: httpx.AsyncClient,
        *,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        timeout: httpx.Timeout,
    ) -> httpx.Response:
        try:
            return await client.post(
                self.config.api_url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise GroqAPIError(
                "Groq request timed out. Try again or use the fallback model.",
            ) from exc
        except httpx.HTTPError as exc:
            raise GroqAPIError(f"Groq request failed: {exc}") from exc

    def _parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        if response.status_code >= 400:
            raise self._build_http_error(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise GroqAPIError("Groq returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise GroqAPIError("Groq returned an invalid response format")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise GroqAPIError("Groq response did not include any choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise GroqAPIError("Groq response choice was not an object")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise GroqAPIError("Groq response did not include a valid message object")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise GroqAPIError("Groq response did not include message content")

        return {
            "model": data.get("model", ""),
            "content": content,
            "raw": data,
        }

    def _build_http_error(self, response: httpx.Response) -> GroqAPIError:
        status_code = response.status_code
        detail = ""

        try:
            data = response.json()
        except ValueError:
            data = None

        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                detail = str(error.get("message", "")).strip()
            elif error:
                detail = str(error).strip()

        if not detail:
            detail = response.text.strip() or "Unknown Groq API error"

        if status_code == 401:
            message = "Groq authentication failed. Check GROQ_API_KEY."
        elif status_code == 429:
            message = f"Groq rate limit reached: {detail}"
        else:
            message = f"Groq API error ({status_code}): {detail}"

        return GroqAPIError(message, status_code=status_code)
