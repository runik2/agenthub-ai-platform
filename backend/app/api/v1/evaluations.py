from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, workspace_owner_id
from app.core.errors import AppError
from app.db.models import Agent, EvaluationCase, EvaluationRun, LLMProvider, User
from app.db.session import get_session
from app.schemas.evaluations import EvaluationCaseCreate, EvaluationCaseOut, EvaluationRunOut
from app.services import llm
from app.services.pricing import compute_cost

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


async def owned_case(case_id: str, user: User, session: AsyncSession) -> EvaluationCase:
    case = await session.scalar(
        select(EvaluationCase).where(
            EvaluationCase.id == case_id, EvaluationCase.owner_id == workspace_owner_id(user)
        )
    )
    if not case:
        raise AppError("EVALUATION_NOT_FOUND", "Evaluation case not found", 404)
    return case


@router.get("/cases", response_model=list[EvaluationCaseOut])
async def list_cases(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return list(
        (
            await session.scalars(
                select(EvaluationCase)
                .where(EvaluationCase.owner_id == workspace_owner_id(user))
                .order_by(EvaluationCase.created_at.desc())
            )
        ).all()
    )


@router.post("/cases", response_model=EvaluationCaseOut, status_code=201)
async def create_case(
    payload: EvaluationCaseCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not await session.scalar(
        select(Agent.id).where(Agent.id == payload.agent_id, Agent.owner_id == workspace_owner_id(user))
    ):
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)
    case = EvaluationCase(owner_id=workspace_owner_id(user), **payload.model_dump())
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


@router.get("/runs", response_model=list[EvaluationRunOut])
async def list_runs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return list(
        (
            await session.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.owner_id == workspace_owner_id(user))
                .order_by(EvaluationRun.created_at.desc())
                .limit(100)
            )
        ).all()
    )


@router.post("/cases/{case_id}/run", response_model=EvaluationRunOut, status_code=201)
async def run_case(
    case_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    case = await owned_case(case_id, user, session)
    agent = await session.get(Agent, case.agent_id)
    provider = await session.get(LLMProvider, agent.provider_id) if agent and agent.provider_id else None
    if not agent or not provider or provider.owner_id != workspace_owner_id(user) or not provider.is_active:
        raise AppError("EVALUATION_NO_PROVIDER", "Agent needs an active model provider", 409)
    run = EvaluationRun(
        owner_id=workspace_owner_id(user), case_id=case.id, agent_id=agent.id, status="running"
    )
    session.add(run)
    await session.flush()
    try:
        result = await llm.chat(
            provider,
            agent.model_name or provider.default_model,
            [{"role": "system", "content": agent.system_prompt}, {"role": "user", "content": case.prompt}],
            agent.temperature,
            agent.max_tokens,
        )
        run.status = "completed"
        run.output = result.content
        run.latency_ms = result.latency_ms
        run.cost = compute_cost(
            result.tokens_in, result.tokens_out, provider.input_price_per_1m, provider.output_price_per_1m
        )
        run.passed = not case.expected.strip() or case.expected.lower() in result.content.lower()
    except llm.LLMError as exc:
        run.status = "error"
        run.error = exc.message
    await session.commit()
    await session.refresh(run)
    return run
