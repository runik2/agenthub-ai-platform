from __future__ import annotations

import httpx

from app.config import get_settings
from app.core.crypto import decrypt_value
from app.db.models import LLMProvider

_transport: httpx.AsyncBaseTransport | None = None


class EmbeddingError(Exception):
    pass


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


def _base_url(provider: LLMProvider) -> str:
    base = (provider.base_url or "").strip().rstrip("/")
    if provider.kind == "ollama" and base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    if not base:
        raise EmbeddingError("Embedding provider base_url is empty")
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


async def embed(provider: LLMProvider, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    base = _base_url(provider)
    model = provider.default_model
    if not model:
        raise EmbeddingError("Embedding model is not configured")
    timeout = httpx.Timeout(get_settings().llm_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, transport=_transport) as client:
        try:
            if provider.kind == "ollama":
                vectors = []
                for text in texts:
                    response = await client.post(
                        f"{base}/api/embeddings",
                        headers=_headers(provider),
                        json={"model": model, "prompt": text},
                    )
                    response.raise_for_status()
                    vectors.append([float(value) for value in response.json().get("embedding", [])])
            else:
                response = await client.post(
                    f"{base}/embeddings",
                    headers=_headers(provider),
                    json={"model": model, "input": texts},
                )
                response.raise_for_status()
                vectors = [
                    [float(value) for value in item.get("embedding", [])]
                    for item in response.json().get("data", [])
                ]
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise EmbeddingError(f"Embedding provider failed: {exc}") from exc
    if len(vectors) != len(texts) or any(not vector for vector in vectors):
        raise EmbeddingError("Embedding provider returned an invalid vector response")
    return vectors
