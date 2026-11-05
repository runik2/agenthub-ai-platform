from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, workspace_owner_id
from app.core.errors import AppError
from app.db.models import Agent, EvaluationCase, EvaluationRun, LLMProvider, PromptVersion, User
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
    case_id: str,
    prompt_version_id: str | None = Query(default=None),
    provider_id: str | None = Query(default=None),
    model_name: str | None = Query(default=None, max_length=255),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    case = await owned_case(case_id, user, session)
    agent = await session.get(Agent, case.agent_id)
    provider = await session.get(LLMProvider, provider_id or agent.provider_id) if agent else None
    if not agent or not provider or provider.owner_id != workspace_owner_id(user) or not provider.is_active:
        raise AppError("EVALUATION_NO_PROVIDER", "Agent needs an active model provider", 409)
    prompt_version = None
    if prompt_version_id:
        prompt_version = await session.scalar(
            select(PromptVersion).where(
                PromptVersion.id == prompt_version_id,
                PromptVersion.agent_id == agent.id,
                PromptVersion.owner_id == workspace_owner_id(user),
            )
        )
        if not prompt_version:
            raise AppError("PROMPT_VERSION_NOT_FOUND", "Prompt version not found", 404)
    run = EvaluationRun(
        owner_id=workspace_owner_id(user),
        case_id=case.id,
        agent_id=agent.id,
        provider_id=provider.id,
        prompt_version_id=prompt_version.id if prompt_version else None,
        status="running",
    )
    session.add(run)
    await session.flush()
    try:
        result = await llm.chat(
            provider,
            model_name or agent.model_name or provider.default_model,
            [
                {
                    "role": "system",
                    "content": prompt_version.system_prompt
                    if prompt_version
                    else agent.system_prompt,
                },
                {"role": "user", "content": case.prompt},
            ],
            agent.temperature,
            agent.max_tokens,
        )
        run.status = "completed"
        run.output = result.content
        run.model_name = result.model
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


@router.post("/batch", response_model=list[EvaluationRunOut], status_code=201)
async def run_batch(
    case_ids: list[str] = Query(..., min_length=1, max_length=50),
    prompt_version_id: str | None = Query(default=None),
    provider_id: str | None = Query(default=None),
    model_name: str | None = Query(default=None, max_length=255),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    unique_ids = list(dict.fromkeys(case_ids))
    if len(unique_ids) > 50:
        raise AppError("EVALUATION_BATCH_TOO_LARGE", "Batch is limited to 50 cases", 422)
    return [
        await run_case(case_id, prompt_version_id, provider_id, model_name, user, session)
        for case_id in unique_ids
    ]


@router.get("/summary")
async def evaluation_summary(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    runs = list(
        (
            await session.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.owner_id == workspace_owner_id(user))
                .order_by(EvaluationRun.created_at.desc())
                .limit(500)
            )
        ).all()
    )
    completed = [run for run in runs if run.status == "completed"]
    total_cost = sum(float(run.cost or 0) for run in completed)
    return {
        "runs": len(runs),
        "completed": len(completed),
        "passed": sum(int(run.passed) for run in completed),
        "pass_rate": round(sum(int(run.passed) for run in completed) / len(completed), 4)
        if completed
        else 0,
        "avg_latency_ms": round(sum(run.latency_ms for run in completed) / len(completed), 1)
        if completed
        else 0,
        "total_cost": round(total_cost, 6),
        "by_prompt_version": [
            {
                "prompt_version_id": version_id or "current",
                "runs": len(group),
                "passed": sum(int(run.passed) for run in group),
                "pass_rate": round(sum(int(run.passed) for run in group) / len(group), 4),
                "avg_latency_ms": round(sum(run.latency_ms for run in group) / len(group), 1),
                "cost": round(sum(float(run.cost or 0) for run in group), 6),
            }
            for version_id, group in _group_runs(completed)
        ],
    }


def _group_runs(runs: list[EvaluationRun]) -> list[tuple[str | None, list[EvaluationRun]]]:
    groups: dict[str | None, list[EvaluationRun]] = {}
    for run in runs:
        groups.setdefault(run.prompt_version_id, []).append(run)
    return list(groups.items())
