from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.config import get_settings

logger = logging.getLogger("agenthub.email")


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def send_password_reset_email(to_email: str, token: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("SMTP is not configured; password reset email was not sent")
        return False
    reset_url = f"{settings.password_reset_frontend_url}?reset_token={quote(token)}"
    body = (
        "Здравствуйте!\n\n"
        "Для смены пароля AgentHub откройте ссылку:\n"
        f"{reset_url}\n\n"
        f"Ссылка действительна {settings.password_reset_ttl_minutes} минут.\n"
        "Если вы не запрашивали смену пароля, проигнорируйте это письмо."
    )
    try:
        await asyncio.to_thread(_send_smtp, to_email, "AgentHub: восстановление пароля", body)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Password reset email delivery failed")
        return False


async def send_notification_email(to_email: str, subject: str, body: str) -> bool:
    """Best-effort operational notification; SMTP remains optional in local mode."""
    if not get_settings().smtp_host:
        logger.info("SMTP is not configured; notification email was skipped")
        return False
    try:
        await asyncio.to_thread(_send_smtp, to_email, subject[:160], body[:10_000])
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Notification email delivery failed")
        return False
