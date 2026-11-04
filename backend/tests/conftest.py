from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import httpx
import pytest

TEST_DB = Path(tempfile.gettempdir()) / "agenthub_pytest.db"

os.environ.update(
    {
        "APP_MODE": "local",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DB.as_posix()}",
        "JWT_SECRET": "pytest-secret-key-with-enough-entropy-0123456789",
        "SECRET_ENCRYPTION_KEY": "",
        "SEED_DEMO_DATA": "false",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@test.local",
        "BOOTSTRAP_ADMIN_PASSWORD": "admin12345",
        "BOOTSTRAP_ADMIN_NAME": "Test Admin",
        "LOG_LEVEL": "WARNING",
    }
)

from app.config import get_settings, reset_settings_cache  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import dispose_engine, get_session_factory, init_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import llm  # noqa: E402

reset_settings_cache()
get_settings()
app = create_app()


@pytest.fixture(scope="session", autouse=True)
def clean_database() -> None:
    if TEST_DB.exists():
        TEST_DB.unlink()
    asyncio.run(_prepare_database())


async def _prepare_database() -> None:
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            User(
                email="admin@test.local",
                hashed_password=hash_password("admin12345"),
                full_name="Test Admin",
                role="admin",
                is_active=True,
            )
        )
        await session.commit()
    await dispose_engine()


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dispose_engine()


@pytest.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "admin12345"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def ollama_answer(content: str = "Mock answer from the model.", tokens_in: int = 42, tokens_out: int = 11):
    payload = {
        "model": "llama3.2:3b",
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": tokens_in,
        "eval_count": tokens_out,
        "done": True,
    }
    return httpx.Response(
        200, content=json.dumps(payload).encode(), headers={"content-type": "application/json"}
    )


@pytest.fixture
def mock_llm():
    """Replaces outbound HTTP with a transport; override `handler` inside a test."""
    state = {"handler": lambda request: ollama_answer()}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        return state["handler"](request)

    llm.set_transport(httpx.MockTransport(transport_handler))
    yield state
    llm.set_transport(None)


async def raw_usage_rows() -> list[dict]:
    from sqlalchemy import select

    from app.db.models import LLMUsage

    async with get_session_factory()() as session:
        rows = (await session.scalars(select(LLMUsage).order_by(LLMUsage.created_at.desc()))).all()
        return [
            {
                "status": row.status,
                "error_code": row.error_code,
                "tokens_in": row.tokens_in,
                "tokens_out": row.tokens_out,
                "cost": float(row.cost),
                "agent_id": row.agent_id,
            }
            for row in rows
        ]
