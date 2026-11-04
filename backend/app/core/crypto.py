from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger("agenthub.crypto")


def _derive_fernet() -> Fernet:
    settings = get_settings()
    raw = settings.secret_encryption_key.strip()
    if raw:
        try:
            key = base64.urlsafe_b64decode(raw.encode())
            if len(key) == 32:
                return Fernet(raw.encode())
        except (ValueError, TypeError):
            logger.warning("SECRET_ENCRYPTION_KEY is not valid base64, deriving from JWT_SECRET")
    digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(value: str) -> str:
    return _derive_fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str | None:
    try:
        return _derive_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        logger.warning("stored provider credential could not be decrypted")
        return None


def key_hint(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return f"***{value[-4:]}"
