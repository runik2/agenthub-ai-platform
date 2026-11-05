from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import workspace_owner_id
from app.db.models import Agent, LLMUsage, User


async def current_budget(session: AsyncSession, user: User) -> dict:
    owner_id = workspace_owner_id(user)
    owner = await session.get(User, owner_id)
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tokens, cost = (
        await session.execute(
            select(
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                func.coalesce(func.sum(LLMUsage.cost), 0),
            )
            .join(Agent, Agent.id == LLMUsage.agent_id)
            .where(Agent.owner_id == owner_id, LLMUsage.created_at >= start)
        )
    ).one()
    token_limit = int(owner.monthly_token_limit or 0) if owner else 0
    cost_limit = Decimal(owner.monthly_cost_limit or 0) if owner else Decimal("0")
    warning_percent = int(owner.budget_warning_percent or 80) if owner else 80
    token_ratio = float(tokens or 0) / token_limit if token_limit else 0
    cost_ratio = float(cost or 0) / float(cost_limit) if cost_limit else 0
    ratio = max(token_ratio, cost_ratio)
    return {
        "tokens": int(tokens or 0),
        "cost": float(cost or 0),
        "token_limit": token_limit,
        "cost_limit": float(cost_limit),
        "warning_percent": warning_percent,
        "ratio": round(ratio, 4),
        "status": "exceeded" if ratio >= 1 else "warning" if ratio >= warning_percent / 100 else "ok",
    }
