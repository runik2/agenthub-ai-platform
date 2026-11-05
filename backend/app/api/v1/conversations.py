from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, workspace_owner_id, write_audit
from app.core.errors import AppError
from app.core.pagination import Pagination, paginate
from app.db.models import Agent, Conversation, Message, User
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
