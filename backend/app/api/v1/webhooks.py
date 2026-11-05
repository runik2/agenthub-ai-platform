from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from ipaddress import ip_address, ip_network

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, workspace_owner_id
from app.config import get_settings
from app.core.crypto import decrypt_value, encrypt_value
from app.core.errors import AppError
from app.db.models import IntegrationTool, Task, User, WebhookDelivery, WebhookEndpoint, Workflow
from app.db.session import get_session
from app.queue.runtime import get_queue
from app.schemas.webhooks import (
    DeliveryOut,
    WebhookCreate,
    WebhookCreated,
    WebhookOut,
    WebhookTestOut,
    WebhookTestPayload,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
incoming_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def workflow_needs_approval(session: AsyncSession, workflow: Workflow | None, owner_id: str) -> bool:
    if not workflow:
        return False
    if any(step.get("type") == "approval" for step in workflow.steps or []):
        return True
    tool_ids = [step.get("tool_id") for step in workflow.steps or [] if step.get("tool_id")]
    return bool(
        tool_ids
        and await session.scalar(
            select(IntegrationTool.id).where(
                IntegrationTool.id.in_(tool_ids),
                IntegrationTool.owner_id == owner_id,
                IntegrationTool.requires_approval.is_(True),
            )
        )
    )


@router.get("/endpoints", response_model=list[WebhookOut])
async def list_endpoints(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return list(
        (
            await session.scalars(
                select(WebhookEndpoint)
                .where(WebhookEndpoint.owner_id == workspace_owner_id(user))
                .order_by(WebhookEndpoint.created_at.desc())
            )
        ).all()
    )


@router.post("/endpoints", response_model=WebhookCreated, status_code=201)
async def create_endpoint(
    payload: WebhookCreate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    try:
        for rule in payload.allowed_ips:
            ip_network(rule, strict=False)
    except ValueError as exc:
        raise AppError(
            "INVALID_WEBHOOK_IP",
            "Webhook IP rules must be valid IP addresses or CIDR ranges",
            422,
        ) from exc
    workflow = await session.scalar(
        select(Workflow).where(
            Workflow.id == payload.workflow_id, Workflow.owner_id == workspace_owner_id(user)
        )
    )
    if not workflow:
        raise AppError("WORKFLOW_NOT_FOUND", "Workflow not found", 404)
    if await session.scalar(
        select(WebhookEndpoint.id).where(
            WebhookEndpoint.owner_id == workspace_owner_id(user), WebhookEndpoint.slug == payload.slug
        )
    ):
        raise AppError("WEBHOOK_SLUG_IN_USE", "Webhook slug is already in use", 409)
    secret = secrets.token_urlsafe(32)
    endpoint = WebhookEndpoint(
        owner_id=workspace_owner_id(user), secret_encrypted=encrypt_value(secret), **payload.model_dump()
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
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.owner_id == workspace_owner_id(user)
        )
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


@router.post("/endpoints/{endpoint_id}/deliveries/{delivery_id}/retry", response_model=DeliveryOut)
async def retry_delivery(
    endpoint_id: str,
    delivery_id: str,
    user: User = Depends(require_roles("admin", "manager", "operator")),
    session: AsyncSession = Depends(get_session),
) -> WebhookDelivery:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.owner_id == workspace_owner_id(user)
        )
    )
    delivery = await session.scalar(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id, WebhookDelivery.endpoint_id == endpoint_id
        )
    )
    if not endpoint or not delivery:
        raise AppError("WEBHOOK_DELIVERY_NOT_FOUND", "Webhook delivery not found", 404)
    if not delivery.signature_valid:
        raise AppError("WEBHOOK_RETRY_UNSAFE", "Rejected deliveries cannot be retried", 409)
    if delivery.status not in {"failed"}:
        raise AppError("WEBHOOK_RETRY_NOT_AVAILABLE", "Only failed deliveries can be retried", 409)
    workflow = await session.get(Workflow, endpoint.workflow_id)
    requires_approval = await workflow_needs_approval(session, workflow, endpoint.owner_id)
    task = Task(
        owner_id=endpoint.owner_id,
        workflow_id=endpoint.workflow_id,
        name=f"Webhook retry: {endpoint.name}",
        input=json.dumps(delivery.payload, ensure_ascii=False),
        requires_approval=requires_approval,
        status="waiting_approval" if requires_approval else "pending",
    )
    session.add(task)
    await session.flush()
    delivery.task_id = task.id
    delivery.status = "waiting_approval" if requires_approval else "retrying"
    delivery.error = None
    await session.commit()
    if not requires_approval:
        try:
            await get_queue().enqueue("execute_task", {"task_id": task.id})
        except Exception as exc:
            task.status, task.error = "failed", str(exc)
            delivery.status, delivery.error = "failed", str(exc)
            await session.commit()
    await session.refresh(delivery)
    return delivery


@router.post("/endpoints/{endpoint_id}/test", response_model=WebhookTestOut, status_code=202)
async def test_endpoint(
    endpoint_id: str,
    payload: WebhookTestPayload,
    user: User = Depends(require_roles("admin", "manager", "operator")),
    session: AsyncSession = Depends(get_session),
) -> WebhookTestOut:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.owner_id == workspace_owner_id(user),
            WebhookEndpoint.enabled.is_(True),
        )
    )
    if not endpoint:
        raise AppError("WEBHOOK_NOT_FOUND", "Webhook endpoint not found", 404)
    workflow = await session.get(Workflow, endpoint.workflow_id)
    requires_approval = await workflow_needs_approval(session, workflow, endpoint.owner_id)
    task = Task(
        owner_id=endpoint.owner_id,
        workflow_id=endpoint.workflow_id,
        name=f"Webhook test: {endpoint.name}",
        input=json.dumps(payload.payload, ensure_ascii=False),
        requires_approval=requires_approval,
        status="waiting_approval" if requires_approval else "pending",
    )
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        status="waiting_approval" if requires_approval else "accepted",
        signature_valid=True,
        payload=payload.payload,
    )
    session.add_all([task, delivery])
    await session.flush()
    delivery.task_id = task.id
    endpoint.last_received_at = datetime.now(UTC)
    await session.commit()
    if not requires_approval:
        try:
            await get_queue().enqueue("execute_task", {"task_id": task.id})
        except Exception as exc:
            task.status, task.error = "failed", str(exc)
            delivery.status, delivery.error = "failed", str(exc)
            await session.commit()
            raise AppError("WEBHOOK_QUEUE_ERROR", "Webhook test could not be queued", 503) from exc
    return WebhookTestOut(status=delivery.status, task_id=task.id, delivery_id=delivery.id)


@incoming_router.post("/incoming/{slug}")
async def receive_webhook(
    slug: str,
    request: Request,
    x_agenthub_signature: str | None = Header(default=None),
    x_agenthub_event_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.slug == slug, WebhookEndpoint.enabled.is_(True))
    )
    if not endpoint:
        raise AppError("WEBHOOK_NOT_FOUND", "Webhook endpoint not found", 404)
    if endpoint.allowed_ips:
        client_host = request.client.host if request.client else ""
        try:
            source_ip = ip_address(client_host)
            allowed = any(source_ip in ip_network(rule, strict=False) for rule in endpoint.allowed_ips)
        except ValueError:
            allowed = False
        if not allowed:
            session.add(
                WebhookDelivery(
                    endpoint_id=endpoint.id,
                    status="rejected",
                    signature_valid=False,
                    payload={},
                    error="Source IP is not allowlisted",
                )
            )
            await session.commit()
            raise AppError("WEBHOOK_IP_NOT_ALLOWED", "Source IP is not allowed for this webhook", 403)
    if x_agenthub_event_id and len(x_agenthub_event_id) > 200:
        raise AppError("INVALID_WEBHOOK_EVENT_ID", "Webhook event id is too long", 422)
    max_body = max(1, get_settings().webhook_max_body_bytes)
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_body:
        raise AppError("WEBHOOK_PAYLOAD_TOO_LARGE", "Webhook payload is too large", 413)
    raw = await request.body()
    if len(raw) > max_body:
        raise AppError("WEBHOOK_PAYLOAD_TOO_LARGE", "Webhook payload is too large", 413)
    secret = decrypt_value(endpoint.secret_encrypted)
    expected = "sha256=" + hmac.new((secret or "").encode(), raw, hashlib.sha256).hexdigest()
    valid = bool(secret and x_agenthub_signature and hmac.compare_digest(expected, x_agenthub_signature))
    if not valid:
        session.add(
            WebhookDelivery(
                endpoint_id=endpoint.id,
                status="rejected",
                signature_valid=False,
                payload={},
                error="Invalid HMAC signature",
            )
        )
        await session.commit()
        raise AppError("INVALID_WEBHOOK_SIGNATURE", "Invalid webhook signature", 401)
    try:
        payload = json.loads(raw.decode() or "{}") if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppError("INVALID_WEBHOOK_PAYLOAD", "Webhook body must be valid JSON", 400) from exc
    if x_agenthub_event_id:
        existing = await session.scalar(
            select(WebhookDelivery).where(
                WebhookDelivery.endpoint_id == endpoint.id,
                WebhookDelivery.event_id == x_agenthub_event_id,
            )
        )
        if existing:
            return {"status": "duplicate", "task_id": existing.task_id or ""}
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event_id=x_agenthub_event_id,
        status="rejected" if not valid else "accepted",
        signature_valid=valid,
        payload=payload if isinstance(payload, dict) else {"value": payload},
    )
    session.add(delivery)
    workflow = await session.get(Workflow, endpoint.workflow_id)
    requires_approval = await workflow_needs_approval(session, workflow, endpoint.owner_id)
    task = Task(
        owner_id=endpoint.owner_id,
        workflow_id=endpoint.workflow_id,
        name=f"Webhook: {endpoint.name}",
        input=raw.decode(),
        requires_approval=requires_approval,
        status="waiting_approval" if requires_approval else "pending",
    )
    session.add(task)
    endpoint.last_received_at = datetime.now(UTC)
    await session.flush()
    delivery.task_id = task.id
    if requires_approval:
        delivery.status = "waiting_approval"
    await session.commit()
    if requires_approval:
        return {"status": "waiting_approval", "task_id": task.id}
    try:
        await get_queue().enqueue("execute_task", {"task_id": task.id})
    except Exception as exc:
        task.status, task.error = "failed", str(exc)
        delivery.status, delivery.error = "failed", str(exc)
        await session.commit()
        raise AppError("WEBHOOK_QUEUE_ERROR", "Webhook could not be queued", 503) from exc
    return {"status": "accepted", "task_id": task.id}
