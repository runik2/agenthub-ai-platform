from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import workspace_owner_id
from app.core.errors import AppError
from app.db.models import (
    Agent,
    AgentMemory,
    Conversation,
    KnowledgeChunk,
    KnowledgeDocument,
    LLMProvider,
    LLMUsage,
    Message,
    User,
)
from app.services import embeddings, llm
from app.services.pricing import compute_cost

HISTORY_LIMIT = 20
FALLBACK_NOTICE_LIMIT = 60


def _title_from(text: str) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= FALLBACK_NOTICE_LIMIT:
        return clean or "New conversation"
    return clean[:FALLBACK_NOTICE_LIMIT].rstrip() + "…"


def build_history(
    agent: Agent,
    messages: list[Message],
    memories: list[AgentMemory],
    knowledge: list[tuple[KnowledgeChunk, str]] | None = None,
) -> list[dict[str, str]]:
    memory_context = "\n".join(f"- {memory.content}" for memory in memories)
    system_prompt = agent.system_prompt
    if memory_context:
        system_prompt += f"\n\nRelevant saved facts (use only when useful):\n{memory_context}"
    if knowledge:
        source_context = "\n".join(
            f"[{title} · chunk {chunk.chunk_index + 1}] {chunk.content}" for chunk, title in knowledge
        )
        system_prompt += (
            "\n\nKnowledge base excerpts (cite the source title when relevant; "
            f"do not invent details):\n{source_context}"
        )
    payload: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for message in messages[-HISTORY_LIMIT:]:
        if message.role in {"user", "assistant"} and message.content:
            payload.append({"role": message.role, "content": message.content})
    return payload


async def send_message(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    content: str,
) -> dict:
    agent = await session.get(Agent, conversation.agent_id)
    if agent is None:
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)
    if not agent.provider_id:
        raise AppError("AGENT_NO_PROVIDER", "This agent has no model provider attached", 409)

    provider = await session.get(LLMProvider, agent.provider_id)
    if provider is None or provider.owner_id != workspace_owner_id(user):
        raise AppError("PROVIDER_NOT_FOUND", "The provider of this agent no longer exists", 409)
    if not provider.is_active:
        raise AppError("PROVIDER_INACTIVE", "The provider of this agent is disabled", 409)

    now = datetime.now(UTC)
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content.strip(),
        meta={},
    )
    session.add(user_message)
    await session.flush()

    history_rows = (
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        )
    ).all()
    memories = (
        await session.scalars(
            select(AgentMemory)
            .where(
                AgentMemory.owner_id == workspace_owner_id(user),
                or_(AgentMemory.agent_id == agent.id, AgentMemory.agent_id.is_(None)),
            )
            .order_by(AgentMemory.is_pinned.desc(), AgentMemory.updated_at.desc())
            .limit(12)
        )
    ).all()
    words = [word.lower() for word in content.split() if len(word) > 2][:8]
    knowledge: list[tuple[KnowledgeChunk, str]] = []
    chunk_filters = [
        KnowledgeChunk.owner_id == workspace_owner_id(user),
        or_(KnowledgeChunk.agent_id == agent.id, KnowledgeChunk.agent_id.is_(None)),
    ]
    chunk_rows: list[KnowledgeChunk] = []
    if provider.is_active:
        candidate_rows = list(
            (await session.scalars(select(KnowledgeChunk).where(*chunk_filters).limit(100))).all()
        )
        if any(row.embedding for row in candidate_rows):
            try:
                query_vector = (await embeddings.embed(provider, [content]))[0]
                norm_query = math.sqrt(sum(value * value for value in query_vector))
                ranked = []
                for row in candidate_rows:
                    if not row.embedding:
                        continue
                    norm_row = math.sqrt(sum(value * value for value in row.embedding))
                    score = sum(a * b for a, b in zip(query_vector, row.embedding, strict=False))
                    if norm_query and norm_row:
                        ranked.append((score / (norm_query * norm_row), row))
                chunk_rows = [row for _, row in sorted(ranked, key=lambda item: item[0], reverse=True)[:6]]
            except embeddings.EmbeddingError:
                chunk_rows = []
    if not chunk_rows and words:
        matches = or_(*(KnowledgeChunk.content.ilike(f"%{word}%") for word in words))
        chunk_rows = list(
            (await session.scalars(select(KnowledgeChunk).where(*chunk_filters, matches).limit(6))).all()
        )
        document_ids = {chunk.document_id for chunk in chunk_rows}
        titles = (
            dict(
                (
                    await session.execute(
                        select(KnowledgeDocument.id, KnowledgeDocument.title).where(
                            KnowledgeDocument.id.in_(document_ids),
                            KnowledgeDocument.owner_id == workspace_owner_id(user),
                        )
                    )
                ).all()
            )
            if document_ids
            else {}
        )
        knowledge = [(chunk, titles.get(chunk.document_id, "Knowledge base")) for chunk in chunk_rows]
    payload = build_history(agent, list(history_rows), list(memories), knowledge)

    model_name = agent.model_name or provider.default_model
    try:
        result = await llm.chat(
            provider=provider,
            model=model_name,
            messages=payload,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
        )
    except llm.LLMError as exc:
        session.add(
            LLMUsage(
                conversation_id=conversation.id,
                message_id=user_message.id,
                agent_id=agent.id,
                provider_id=provider.id,
                model_name=model_name,
                tokens_in=0,
                tokens_out=0,
                total_tokens=0,
                latency_ms=0,
                cost=Decimal("0"),
                status="error",
                error_code=exc.code,
            )
        )
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.last_message_at = now
        await session.commit()
        raise AppError(exc.code, exc.message, 502) from exc

    cost = compute_cost(
        result.tokens_in,
        result.tokens_out,
        provider.input_price_per_1m,
        provider.output_price_per_1m,
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.content,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        model_name=result.model,
        provider_id=provider.id,
        meta={
            "estimated": result.estimated,
            "raw_usage": result.raw_usage,
            "sources": [
                {"document_id": chunk.document_id, "title": title, "chunk_index": chunk.chunk_index}
                for chunk, title in knowledge
            ],
        },
    )
    session.add(assistant_message)
    await session.flush()

    session.add(
        LLMUsage(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            agent_id=agent.id,
            provider_id=provider.id,
            model_name=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            total_tokens=result.tokens_in + result.tokens_out,
            latency_ms=result.latency_ms,
            cost=cost,
            status="ok",
        )
    )

    conversation.message_count = (conversation.message_count or 0) + 2
    conversation.total_tokens = (conversation.total_tokens or 0) + result.tokens_in + result.tokens_out
    conversation.total_cost = Decimal(conversation.total_cost or 0) + cost
    conversation.last_message_at = now
    if not conversation.title:
        conversation.title = _title_from(content)

    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)

    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "usage": {
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "total_tokens": result.tokens_in + result.tokens_out,
            "cost": float(cost),
            "currency": "USD",
            "latency_ms": result.latency_ms,
            "model_name": result.model,
            "estimated": result.estimated,
        },
    }
