from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Agent, Conversation, LLMProvider, LLMUsage, Message, User
from app.db.session import get_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    agent_ids = select(Agent.id).where(Agent.owner_id == user.id)
    usage_scope = (LLMUsage.agent_id.in_(agent_ids), LLMUsage.created_at >= since)

    totals_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(LLMUsage.tokens_in), 0),
                func.coalesce(func.sum(LLMUsage.tokens_out), 0),
                func.coalesce(func.sum(LLMUsage.cost), 0),
                func.count(LLMUsage.id),
            ).where(*usage_scope)
        )
    ).one()

    agents_count = int(
        await session.scalar(select(func.count(Agent.id)).where(Agent.owner_id == user.id)) or 0
    )
    conversations_count = int(
        await session.scalar(
            select(func.count(Conversation.id)).where(Conversation.user_id == user.id)
        )
        or 0
    )
    messages_count = int(
        await session.scalar(
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.user_id == user.id)
        )
        or 0
    )
    errors_count = int(
        await session.scalar(
            select(func.count(LLMUsage.id)).where(*usage_scope, LLMUsage.status == "error")
        )
        or 0
    )

    day_column = func.date(LLMUsage.created_at)
    series_rows = (
        await session.execute(
            select(
                day_column,
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                func.coalesce(func.sum(LLMUsage.cost), 0),
                func.count(LLMUsage.id),
            )
            .where(*usage_scope)
            .group_by(day_column)
            .order_by(day_column)
        )
    ).all()

    by_day = {
        str(row[0]): {
            "tokens": int(row[1] or 0),
            "cost": float(row[2] or 0),
            "messages": int(row[3] or 0),
        }
        for row in series_rows
    }
    series = []
    today = date.today()
    for offset in range(days - 1, -1, -1):
        key = (today - timedelta(days=offset)).isoformat()
        bucket = by_day.get(key, {"tokens": 0, "cost": 0.0, "messages": 0})
        series.append({"date": key, **bucket})

    top_rows = (
        await session.execute(
            select(
                Agent.id,
                Agent.name,
                Agent.avatar_color,
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                func.coalesce(func.sum(LLMUsage.cost), 0),
                func.count(LLMUsage.id),
            )
            .join(LLMUsage, LLMUsage.agent_id == Agent.id)
            .where(*usage_scope)
            .group_by(Agent.id, Agent.name, Agent.avatar_color)
            .order_by(func.sum(LLMUsage.total_tokens).desc())
            .limit(5)
        )
    ).all()

    provider_rows = (
        await session.execute(
            select(
                LLMProvider.id,
                LLMProvider.name,
                LLMProvider.kind,
                LLMProvider.last_check_status,
                func.count(LLMUsage.id),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                func.coalesce(func.sum(LLMUsage.cost), 0),
            )
            .outerjoin(LLMUsage, LLMUsage.provider_id == LLMProvider.id)
            .group_by(
                LLMProvider.id,
                LLMProvider.name,
                LLMProvider.kind,
                LLMProvider.last_check_status,
            )
            .order_by(LLMProvider.created_at.asc())
        )
    ).all()

    return {
        "range_days": days,
        "totals": {
            "agents": agents_count,
            "conversations": conversations_count,
            "messages": messages_count,
            "requests": int(totals_row[3] or 0),
            "tokens_in": int(totals_row[0] or 0),
            "tokens_out": int(totals_row[1] or 0),
            "tokens": int(totals_row[0] or 0) + int(totals_row[1] or 0),
            "cost": float(Decimal(totals_row[2] or 0)),
            "errors": errors_count,
        },
        "series": series,
        "top_agents": [
            {
                "agent_id": row[0],
                "name": row[1],
                "avatar_color": row[2],
                "tokens": int(row[3] or 0),
                "cost": float(row[4] or 0),
                "messages": int(row[5] or 0),
            }
            for row in top_rows
        ],
        "providers": [
            {
                "provider_id": row[0],
                "name": row[1],
                "kind": row[2],
                "status": row[3],
                "requests": int(row[4] or 0),
                "tokens": int(row[5] or 0),
                "cost": float(row[6] or 0),
            }
            for row in provider_rows
        ],
    }
