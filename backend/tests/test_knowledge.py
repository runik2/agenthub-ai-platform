from __future__ import annotations

import httpx


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

