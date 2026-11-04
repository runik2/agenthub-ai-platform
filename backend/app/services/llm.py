from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings
from app.core.crypto import decrypt_value
from app.db.models import LLMProvider
from app.services.pricing import estimate_tokens

logger = logging.getLogger("agenthub.llm")

# Tests inject an httpx.MockTransport here; production leaves it as None.
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


class LLMError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class LLMResult:
    content: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str
    estimated: bool = False
    raw_usage: dict[str, Any] = field(default_factory=dict)


def _base_url(provider: LLMProvider) -> str:
    base = (provider.base_url or "").strip().rstrip("/")
    if provider.kind == "ollama":
        if base.endswith("/v1"):
            base = base[:-3].rstrip("/")
        if not base:
            base = get_settings().ollama_base_url.rstrip("/")
    if not base:
        raise LLMError("PROVIDER_MISCONFIGURED", "Provider base_url is empty")
    return base


def _headers(provider: LLMProvider) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if provider.api_key_encrypted:
        key = decrypt_value(provider.api_key_encrypted)
        if key:
            headers["Authorization"] = f"Bearer {key}"
    for name, value in (provider.extra_headers or {}).items():
        headers[str(name)] = str(value)
    return headers


def _client() -> httpx.AsyncClient:
    timeout = httpx.Timeout(get_settings().llm_timeout_seconds, connect=10.0)
    return httpx.AsyncClient(timeout=timeout, transport=_transport)


def _network_error(exc: Exception) -> LLMError:
    if isinstance(exc, httpx.TimeoutException):
        return LLMError("PROVIDER_TIMEOUT", "The model provider did not answer in time")
    return LLMError("PROVIDER_UNAVAILABLE", f"Cannot reach the model provider: {exc}")


async def chat(
    provider: LLMProvider,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> LLMResult:
    base = _base_url(provider)
    model_name = model or provider.default_model
    if not model_name:
        raise LLMError("MODEL_NOT_SET", "No model selected for this agent or provider")

    started = time.perf_counter()
    async with _client() as client:
        try:
            if provider.kind == "ollama":
                response = await client.post(
                    f"{base}/api/chat",
                    headers=_headers(provider),
                    json={
                        "model": model_name,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature, "num_predict": max_tokens},
                    },
                )
            else:
                response = await client.post(
                    f"{base}/chat/completions",
                    headers=_headers(provider),
                    json={
                        "model": model_name,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False,
                    },
                )
        except Exception as exc:  # noqa: BLE001 - normalised below
            raise _network_error(exc) from exc

    latency_ms = int((time.perf_counter() - started) * 1000)

    if response.status_code >= 400:
        snippet = response.text[:300]
        logger.warning("provider %s answered %s: %s", provider.name, response.status_code, snippet)
        raise LLMError("PROVIDER_ERROR", f"Provider error {response.status_code}: {snippet}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMError("PROVIDER_BAD_RESPONSE", "Provider returned non-JSON output") from exc

    if provider.kind == "ollama":
        content = str(payload.get("message", {}).get("content", "")).strip()
        tokens_in = int(payload.get("prompt_eval_count") or 0)
        tokens_out = int(payload.get("eval_count") or 0)
        raw_usage = {
            "prompt_eval_count": payload.get("prompt_eval_count"),
            "eval_count": payload.get("eval_count"),
        }
    else:
        choices = payload.get("choices") or []
        content = ""
        if choices:
            content = str(choices[0].get("message", {}).get("content", "")).strip()
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        raw_usage = dict(usage)

    if not content:
        raise LLMError("EMPTY_RESPONSE", "The model returned an empty answer")

    estimated = False
    if tokens_in <= 0:
        tokens_in = estimate_tokens(" ".join(message["content"] for message in messages))
        estimated = True
    if tokens_out <= 0:
        tokens_out = estimate_tokens(content)
        estimated = True

    return LLMResult(
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        model=str(payload.get("model") or model_name),
        estimated=estimated,
        raw_usage=raw_usage,
    )


async def fetch_models(provider: LLMProvider) -> list[str]:
    """Ask the provider which models it serves. Raises LLMError on failure."""
    base = _base_url(provider)
    async with _client() as client:
        try:
            if provider.kind == "ollama":
                response = await client.get(f"{base}/api/tags", headers=_headers(provider))
            else:
                response = await client.get(f"{base}/models", headers=_headers(provider))
        except Exception as exc:  # noqa: BLE001
            raise _network_error(exc) from exc

    if response.status_code >= 400:
        raise LLMError("PROVIDER_ERROR", f"Provider error {response.status_code}: {response.text[:200]}")
    payload = response.json()
    names: list[str] = []
    if provider.kind == "ollama":
        for item in payload.get("models", []):
            name = item.get("name") or item.get("model")
            if name:
                names.append(str(name))
    else:
        for item in payload.get("data", []):
            if item.get("id"):
                names.append(str(item["id"]))
    return sorted(set(names))


async def test_connection(provider: LLMProvider) -> tuple[bool, str, list[str], int]:
    started = time.perf_counter()
    try:
        models = await fetch_models(provider)
    except LLMError as exc:
        return False, exc.message, [], int((time.perf_counter() - started) * 1000)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return True, f"Connected, {len(models)} models available", models, latency_ms
