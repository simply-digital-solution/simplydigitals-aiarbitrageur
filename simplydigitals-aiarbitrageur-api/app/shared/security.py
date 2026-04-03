"""JWT verification — shares the same secret as AIConnoisseur (single sign-on)."""

from __future__ import annotations

from jose import JWTError, jwt

from app.shared.config import get_settings

settings = get_settings()


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT issued by the AIConnoisseur auth service."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise ValueError("Wrong token type")

    return payload
