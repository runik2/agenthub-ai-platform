from __future__ import annotations

import httpx
import pytest

from app.db.models import LLMProvider
from app.services import embeddings


async def test_knowledge_is_chunked_and_searchable(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/knowledge/documents",
        json={"title": "Support playbook", "content": "Refunds are processed within three business days."},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["chunk_count"] == 1

    results = await client.get(
        "/api/v1/knowledge/search", params={"q": "refunds business"}, headers=auth_headers
    )
    assert results.status_code == 200
    assert results.json()[0]["title"] == "Support playbook"
    assert "three business days" in results.json()[0]["content"]


async def test_text_upload_is_indexed(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    uploaded = await client.post(
        "/api/v1/knowledge/documents/upload",
        files={"file": ("policy.txt", b"Refund policy: three business days.", "text/plain")},
        headers=auth_headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["title"] == "policy.txt"
    assert uploaded.json()["chunk_count"] == 1


async def test_document_reindex_creates_version_snapshot(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/knowledge/documents",
        json={"title": "Versioned guide", "content": "First revision."},
        headers=auth_headers,
    )
    document_id = created.json()["id"]
    assert created.json()["version"] == 1
    reindexed = await client.post(f"/api/v1/knowledge/documents/{document_id}/reindex", headers=auth_headers)
    assert reindexed.status_code == 200
    assert reindexed.json()["version"] == 2
    versions = await client.get(f"/api/v1/knowledge/documents/{document_id}/versions", headers=auth_headers)
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]


@pytest.mark.asyncio
async def test_openai_compatible_embeddings_are_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/embeddings"
        return httpx.Response(
            200,
            json={"data": [{"embedding": [1.0, 0.0]}, {"embedding": [0.0, 1.0]}]},
        )

    embeddings.set_transport(httpx.MockTransport(handler))
    try:
        vectors = await embeddings.embed(
            LLMProvider(
                kind="openai_compatible",
                base_url="https://models.example.test",
                default_model="embed-v1",
            ),
            ["first", "second"],
        )
    finally:
        embeddings.set_transport(None)
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
