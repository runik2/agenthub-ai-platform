from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, workspace_owner_id, write_audit
from app.core.errors import AppError
from app.core.pagination import Pagination, paginate
from app.db.models import Agent, Conversation, LLMProvider, Message, User
from app.db.session import get_session
from app.schemas.common import Page, StatusResponse
from app.schemas.conversations import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services import chat as chat_service
from app.services import llm
from app.services.pricing import compute_cost, estimate_tokens

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_conversation(session: AsyncSession, user: User, conversation_id: str) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conversation is None:
        raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found", 404)
    return conversation


@router.get("", response_model=Page[ConversationOut])
async def list_conversations(
    pagination: Pagination = Depends(),
    agent_id: str = Query(default="", max_length=36),
    search: str = Query(default="", max_length=120),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[ConversationOut]:
    stmt = select(Conversation).where(Conversation.user_id == user.id)
    if agent_id.strip():
        stmt = stmt.where(Conversation.agent_id == agent_id.strip())
    if search.strip():
        stmt = stmt.where(Conversation.title.ilike(f"%{search.strip().lower()}%"))
    stmt = stmt.order_by(Conversation.updated_at.desc())
    rows, total, pages = await paginate(session, stmt, pagination)
    return Page[ConversationOut](
        items=[ConversationOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.post("", response_model=ConversationDetail, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    agent = await session.scalar(
        select(Agent).where(Agent.id == payload.agent_id, Agent.owner_id == workspace_owner_id(user))
    )
    if agent is None:
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)
    conversation = Conversation(
        agent_id=agent.id,
        user_id=user.id,
        title=payload.title.strip(),
        status="active",
        message_count=0,
        total_tokens=0,
        total_cost=0,
    )
    session.add(conversation)
    await session.flush()
    await write_audit(
        session,
        request,
        user.id,
        "conversation.created",
        "conversation",
        conversation.id,
        {"agent_id": agent.id},
    )
    await session.commit()
    await session.refresh(conversation)
    detail = ConversationDetail(**ConversationOut.model_validate(conversation).model_dump())
    return detail


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    conversation = await _get_conversation(session, user, conversation_id)
    messages = (
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        )
    ).all()
    detail = ConversationDetail(**ConversationOut.model_validate(conversation).model_dump())
    detail.messages = [MessageOut.model_validate(message) for message in messages]
    return detail


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationOut:
    conversation = await _get_conversation(session, user, conversation_id)
    conversation.title = payload.title.strip()
    await session.commit()
    await session.refresh(conversation)
    return ConversationOut.model_validate(conversation)


@router.delete("/{conversation_id}", response_model=StatusResponse)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    conversation = await _get_conversation(session, user, conversation_id)
    await session.delete(conversation)
    await write_audit(session, request, user.id, "conversation.deleted", "conversation", conversation_id)
    await session.commit()
    return StatusResponse()


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SendMessageResponse:
    conversation = await _get_conversation(session, user, conversation_id)
    result = await chat_service.send_message(session, user, conversation, payload.content)
    return SendMessageResponse(
        user_message=MessageOut.model_validate(result["user_message"]),
        assistant_message=MessageOut.model_validate(result["assistant_message"]),
        usage=result["usage"],
    )


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream provider chunks as SSE and persist the completed assistant reply."""
    conversation = await _get_conversation(session, user, conversation_id)
    agent = await session.get(Agent, conversation.agent_id)
    if agent is None or not agent.provider_id:
        raise AppError("AGENT_NO_PROVIDER", "This agent has no model provider attached", 409)
    provider = await session.get(LLMProvider, agent.provider_id)
    if provider is None or not provider.is_active or provider.owner_id != workspace_owner_id(user):
        raise AppError("PROVIDER_NOT_FOUND", "The provider of this agent is unavailable", 409)

    user_message = Message(
        conversation_id=conversation.id, role="user", content=payload.content.strip(), meta={}
    )
    session.add(user_message)
    await session.flush()
    history = list(
        (
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.asc())
            )
        ).all()
    )
    messages = chat_service.build_history(agent, history, [], [])
    started = time.perf_counter()
    model_name = agent.model_name or provider.default_model

    async def events():
        chunks: list[str] = []
        try:
            yield "event: start\ndata: {}\n\n"
            async for chunk in llm.stream_tokens(
                provider, model_name, messages, agent.temperature, agent.max_tokens
            ):
                chunks.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            content = "".join(chunks).strip()
            if not content:
                raise llm.LLMError("EMPTY_RESPONSE", "The model returned an empty answer")
            tokens_in = estimate_tokens(" ".join(item["content"] for item in messages))
            tokens_out = estimate_tokens(content)
            latency_ms = int((time.perf_counter() - started) * 1000)
            cost = compute_cost(
                tokens_in, tokens_out, provider.input_price_per_1m, provider.output_price_per_1m
            )
            assistant = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                model_name=model_name,
                provider_id=provider.id,
                meta={"estimated": True, "streamed": True},
            )
            session.add(assistant)
            conversation.message_count = (conversation.message_count or 0) + 2
            conversation.total_tokens = (conversation.total_tokens or 0) + tokens_in + tokens_out
            conversation.total_cost = (conversation.total_cost or 0) + cost
            conversation.last_message_at = datetime.now(UTC)
            if not conversation.title:
                conversation.title = payload.content.strip()[:60]
            await session.commit()
            done_data = json.dumps(
                {
                    "message_id": assistant.id,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": latency_ms,
                },
                ensure_ascii=False,
            )
            yield f"event: done\ndata: {done_data}\n\n"
        except (llm.LLMError, Exception) as exc:
            await session.rollback()
            code = exc.code if isinstance(exc, llm.LLMError) else "STREAM_INTERRUPTED"
            error_data = json.dumps({"code": code, "message": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
