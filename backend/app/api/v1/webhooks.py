from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.crypto import decrypt_value, encrypt_value
from app.core.errors import AppError
from app.db.models import Task, User, WebhookDelivery, WebhookEndpoint, Workflow
from app.db.session import get_session
from app.queue.runtime import get_queue
from app.schemas.webhooks import DeliveryOut, WebhookCreate, WebhookCreated, WebhookOut

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
incoming_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/endpoints", response_model=list[WebhookOut])
async def list_endpoints(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return list(
        (
            await session.scalars(
                select(WebhookEndpoint)
                .where(WebhookEndpoint.owner_id == user.id)
                .order_by(WebhookEndpoint.created_at.desc())
            )
        ).all()
    )


@router.post("/endpoints", response_model=WebhookCreated, status_code=201)
async def create_endpoint(
    payload: WebhookCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workflow = await session.scalar(
        select(Workflow).where(Workflow.id == payload.workflow_id, Workflow.owner_id == user.id)
    )
    if not workflow:
        raise AppError("WORKFLOW_NOT_FOUND", "Workflow not found", 404)
    if await session.scalar(
        select(WebhookEndpoint.id).where(
            WebhookEndpoint.owner_id == user.id, WebhookEndpoint.slug == payload.slug
        )
    ):
        raise AppError("WEBHOOK_SLUG_IN_USE", "Webhook slug is already in use", 409)
    secret = secrets.token_urlsafe(32)
    endpoint = WebhookEndpoint(
        owner_id=user.id, secret_encrypted=encrypt_value(secret), **payload.model_dump()
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return WebhookCreated.model_validate({**endpoint.__dict__, "secret": secret})


@router.get("/endpoints/{endpoint_id}/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    endpoint_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.owner_id == user.id)
    )
    if not endpoint:
        raise AppError("WEBHOOK_NOT_FOUND", "Webhook endpoint not found", 404)
    return list(
        (
            await session.scalars(
                select(WebhookDelivery)
                .where(WebhookDelivery.endpoint_id == endpoint.id)
                .order_by(WebhookDelivery.created_at.desc())
                .limit(100)
            )
        ).all()
    )


@incoming_router.post("/incoming/{slug}")
async def receive_webhook(
    slug: str,
    request: Request,
    x_agenthub_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.slug == slug, WebhookEndpoint.enabled.is_(True))
    )
    if not endpoint:
        raise AppError("WEBHOOK_NOT_FOUND", "Webhook endpoint not found", 404)
    raw = await request.body()
    secret = decrypt_value(endpoint.secret_encrypted)
    expected = "sha256=" + hmac.new((secret or "").encode(), raw, hashlib.sha256).hexdigest()
    valid = bool(secret and x_agenthub_signature and hmac.compare_digest(expected, x_agenthub_signature))
    payload = json.loads(raw.decode() or "{}") if raw else {}
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        status="rejected" if not valid else "accepted",
        signature_valid=valid,
        payload=payload if isinstance(payload, dict) else {"value": payload},
    )
    session.add(delivery)
    if not valid:
        delivery.error = "Invalid HMAC signature"
        await session.commit()
        raise AppError("INVALID_WEBHOOK_SIGNATURE", "Invalid webhook signature", 401)
    task = Task(
        owner_id=endpoint.owner_id,
        workflow_id=endpoint.workflow_id,
        name=f"Webhook: {endpoint.name}",
        input=raw.decode(),
    )
    session.add(task)
    endpoint.last_received_at = datetime.now(UTC)
    await session.flush()
    delivery.task_id = task.id
    await session.commit()
    try:
        await get_queue().enqueue("execute_task", {"task_id": task.id})
    except Exception as exc:
        task.status, task.error = "failed", str(exc)
        delivery.status, delivery.error = "failed", str(exc)
        await session.commit()
        raise AppError("WEBHOOK_QUEUE_ERROR", "Webhook could not be queued", 503) from exc
    return {"status": "accepted", "task_id": task.id}
