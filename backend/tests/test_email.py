from __future__ import annotations

import pytest

from app.config import get_settings
from app.services import email


@pytest.mark.asyncio
async def test_password_reset_email_builds_a_one_time_link(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "password_reset_frontend_url", "https://app.example.test/login")
    sent: dict[str, str] = {}

    def fake_send(to_email: str, subject: str, body: str) -> None:
        sent.update(to=to_email, subject=subject, body=body)

    monkeypatch.setattr(email, "_send_smtp", fake_send)
    assert await email.send_password_reset_email("person@example.test", "token-123") is True
    assert sent["to"] == "person@example.test"
    assert "https://app.example.test/login?reset_token=token-123" in sent["body"]
    assert "AgentHub" in sent["subject"]
