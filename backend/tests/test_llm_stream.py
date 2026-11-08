from __future__ import annotations

import json

import httpx
import pytest

from app.db.models import LLMProvider
from app.services import llm


def provider(kind: str) -> LLMProvider:
    return LLMProvider(
        owner_id="owner",
        name="stream-test",
        kind=kind,
        base_url="http://provider.test/v1" if kind != "ollama" else "http://provider.test",
        default_model="demo-model",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_ollama_stream_yields_ndjson_chunks() -> None:
    body = "\n".join(
        json.dumps({"message": {"content": text}, "done": done})
        for text, done in [("Hello ", False), ("world", True)]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, text=body)

    llm.set_transport(httpx.MockTransport(handler))
    try:
        chunks = [chunk async for chunk in llm.stream_tokens(provider("ollama"), "", [], 0.2, 100)]
    finally:
        llm.set_transport(None)
    assert chunks == ["Hello ", "world"]


@pytest.mark.asyncio
async def test_openai_compatible_stream_yields_sse_deltas() -> None:
    body = "\n".join(
        [
            'data: {"choices":[{"delta":{"content":"Hi "}}]}',
            'data: {"choices":[{"delta":{"content":"there"}}]}',
            "data: [DONE]",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, text=body)

    llm.set_transport(httpx.MockTransport(handler))
    try:
        chunks = [
            chunk
            async for chunk in llm.stream_tokens(provider("openai_compatible"), "", [], 0.2, 100)
        ]
    finally:
        llm.set_transport(None)
    assert chunks == ["Hi ", "there"]


@pytest.mark.asyncio
async def test_stream_provider_error_is_normalized() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    llm.set_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(llm.LLMError, match="Provider error 503"):
            [chunk async for chunk in llm.stream_tokens(provider("ollama"), "", [], 0.2, 100)]
    finally:
        llm.set_transport(None)
