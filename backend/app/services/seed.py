"""Idempotent demo data. Everything created here is explicitly marked as demo."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Agent, Conversation, LLMProvider, LLMUsage, Message, User
from app.services.agent_templates import TEMPLATES_BY_SLUG
from app.services.bootstrap import ensure_bootstrap_admin
from app.services.pricing import compute_cost

logger = logging.getLogger("agenthub.seed")

DEMO_TAG = "demo"
DEMO_PREFIX = "Demo data · "


def _slug(name: str, suffix: str) -> str:
    base = name.lower().replace(" ", "-")
    return f"{base}-{suffix}"


async def seed_demo(session: AsyncSession) -> bool:
    """Returns True when demo rows were created, False when they already existed."""
    settings = get_settings()
    existing = await session.scalar(select(func.count(LLMProvider.id)))
    if existing:
        logger.info("demo seed skipped: providers already present")
        return False

    admin = await ensure_bootstrap_admin(session)
    if admin is None:
        admin = await session.scalar(select(User).order_by(User.created_at.asc()))
    if admin is None:
        logger.info("demo seed skipped: no user to own the demo agents")
        return False

    ollama = LLMProvider(
        name="Ollama (local)",
        kind="ollama",
        base_url=settings.ollama_base_url,
        default_model="llama3.2:3b",
        input_price_per_1m=Decimal("0"),
        output_price_per_1m=Decimal("0"),
        is_active=True,
        last_check_status="unknown",
        models_cache=["llama3.2:3b"],
    )
    openai_demo = LLMProvider(
        name="OpenAI (demo)",
        kind="openai_compatible",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        input_price_per_1m=Decimal("0.15"),
        output_price_per_1m=Decimal("0.60"),
        is_active=False,
        last_check_status="unknown",
        models_cache=["gpt-4o-mini", "gpt-4o"],
        extra_headers={"x-demo-provider": "true"},
    )
    session.add_all([ollama, openai_demo])
    await session.flush()

    demo_agents: list[Agent] = []
    for slug in ["support-agent", "code-reviewer", "data-analyst", "content-writer"]:
        template = TEMPLATES_BY_SLUG[slug]
        agent = Agent(
            name=template.name,
            slug=_slug(template.slug, "demo"),
            description=DEMO_PREFIX + template.description,
            system_prompt=template.system_prompt,
            greeting=template.greeting,
            provider_id=ollama.id,
            model_name=template.model_name,
            temperature=template.temperature,
            max_tokens=template.max_tokens,
            status="active",
            avatar_color=template.avatar_color,
            tags=[*template.tags, DEMO_TAG],
            is_template=False,
            template_slug=template.slug,
            owner_id=admin.id,
        )
        session.add(agent)
        demo_agents.append(agent)
    await session.flush()

    now = datetime.now(UTC)
    conversation_specs = [
        (
            demo_agents[0],
            "Refund for duplicate charge",
            [
                ("user", "I was charged twice for the same subscription. What should I do?"),
                (
                    "assistant",
                    "Sorry about that. Please share the two charge dates and the last four digits "
                    "of the card, and I will check which invoice was duplicated. "
                    "If both charges settled, a refund is issued to the original card within 5–7 days.",
                ),
                ("user", "Charges were on the 2nd and the 3rd, card ending 4417."),
                (
                    "assistant",
                    "Thanks. That looks like a retry after a failed authorisation, which can settle "
                    "twice. I have flagged both payments for reconciliation — the duplicate will be "
                    "refunded automatically, no action needed on your side.",
                ),
            ],
        ),
        (
            demo_agents[1],
            "Review of the auth middleware",
            [
                ("user", "Can you review my JWT middleware? It reads the token from a cookie."),
                (
                    "assistant",
                    "Key risks to check: the cookie must be HttpOnly and SameSite=Lax or stricter, "
                    "the signature algorithm should be pinned, and expiry must be validated. "
                    "Also make sure a missing token returns 401 rather than falling through to an "
                    "anonymous user — that is the most common bypass in this kind of code.",
                ),
            ],
        ),
    ]

    for offset, (agent, title, messages) in enumerate(conversation_specs):
        created = now - timedelta(days=6 - offset * 2, hours=3)
        conversation = Conversation(
            agent_id=agent.id,
            user_id=admin.id,
            title=title,
            status="active",
            message_count=len(messages),
            total_tokens=0,
            total_cost=Decimal("0"),
            last_message_at=created + timedelta(minutes=4 * len(messages)),
            created_at=created,
            updated_at=created,
        )
        session.add(conversation)
        await session.flush()

        total_tokens = 0
        for position, (role, text) in enumerate(messages):
            stamp = created + timedelta(minutes=4 * position)
            tokens_in = 220 + position * 90
            tokens_out = len(text) // 4
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=text,
                tokens_in=tokens_in if role == "assistant" else 0,
                tokens_out=tokens_out if role == "assistant" else 0,
                latency_ms=1400 + position * 260 if role == "assistant" else 0,
                model_name="llama3.2:3b" if role == "assistant" else "",
                provider_id=ollama.id if role == "assistant" else None,
                meta={"demo": True},
                created_at=stamp,
                updated_at=stamp,
            )
            session.add(message)
            await session.flush()
            if role == "assistant":
                total_tokens += tokens_in + tokens_out
                session.add(
                    LLMUsage(
                        conversation_id=conversation.id,
                        message_id=message.id,
                        agent_id=agent.id,
                        provider_id=ollama.id,
                        model_name="llama3.2:3b",
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        total_tokens=tokens_in + tokens_out,
                        latency_ms=message.latency_ms,
                        cost=compute_cost(tokens_in, tokens_out, 0, 0),
                        status="ok",
                        created_at=stamp,
                        updated_at=stamp,
                    )
                )
        conversation.total_tokens = total_tokens

    # A little historical usage so the dashboard chart is not empty on first run.
    rng = random.Random(7)
    for days_ago in range(13, 0, -1):
        for agent in demo_agents[:3]:
            if rng.random() < 0.45:
                continue
            stamp = now - timedelta(days=days_ago, hours=rng.randint(0, 9))
            tokens_in = rng.randint(180, 900)
            tokens_out = rng.randint(120, 700)
            session.add(
                LLMUsage(
                    conversation_id=None,
                    message_id=None,
                    agent_id=agent.id,
                    provider_id=ollama.id,
                    model_name="llama3.2:3b",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    total_tokens=tokens_in + tokens_out,
                    latency_ms=rng.randint(900, 4200),
                    cost=compute_cost(tokens_in, tokens_out, 0, 0),
                    status="ok" if rng.random() > 0.12 else "error",
                    error_code=None if rng.random() > 0.12 else "PROVIDER_TIMEOUT",
                    created_at=stamp,
                    updated_at=stamp,
                )
            )

    await session.commit()
    logger.info("demo seed created for %s", admin.email)
    return True


async def _main() -> None:  # pragma: no cover - manual script entry point
    from app.db.session import get_session_factory, init_db

    logging.basicConfig(level=logging.INFO)
    await init_db()
    async with get_session_factory()() as session:
        created = await seed_demo(session)
    print("demo data created" if created else "demo data already present")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
