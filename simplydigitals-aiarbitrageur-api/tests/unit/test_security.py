"""Test JWT security functions."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone
    UTC = timezone.utc

import pytest
from jose import JWTError, jwt
from unittest.mock import patch

from app.shared.security import decode_token
from app.shared.config import get_settings


class TestJWTTokenDecoding:
    """Test JWT token decoding and verification."""

    def test_decode_valid_token(self) -> None:
        """Test decoding a valid JWT token."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "test-user", "type": "access"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        payload = decode_token(token)
        assert payload.get("sub") == "test-user"
        assert payload.get("type") == "access"

    def test_decode_token_with_correct_type(self) -> None:
        """Test decoding token with correct type claim."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user123", "type": "access"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        payload = decode_token(token, expected_type="access")
        assert payload.get("sub") == "user123"

    def test_decode_token_invalid_signature(self) -> None:
        """Test that invalid signature raises ValueError."""
        # Create token with wrong secret
        invalid_token = jwt.encode(
            {"sub": "test-user", "type": "access"},
            "wrong-secret-key",
            algorithm="HS256",
        )
        
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(invalid_token)

    def test_decode_token_wrong_type(self) -> None:
        """Test that wrong token type raises ValueError."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "test-user", "type": "refresh"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        
        with pytest.raises(ValueError, match="Wrong token type"):
            decode_token(token, expected_type="access")

    def test_decode_malformed_token(self) -> None:
        """Test that malformed token raises ValueError."""
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("malformed.token.here")

    def test_decode_empty_token(self) -> None:
        """Test that empty token raises ValueError."""
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("")


class TestTokenStructure:
    """Test token structure and claims."""

    def test_token_has_type_claim(self) -> None:
        """Test that tokens include type claim."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user1", "type": "access"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        payload = decode_token(token)
        assert "type" in payload

    def test_token_has_sub_claim(self) -> None:
        """Test that tokens include sub claim."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user123", "type": "access"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        payload = decode_token(token)
        assert "sub" in payload
        assert payload["sub"] == "user123"

    def test_decode_default_type_is_access(self) -> None:
        """Test that default expected_type is 'access'."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user1", "type": "access"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        # Should not raise when type is access and no expected_type specified
        payload = decode_token(token)
        assert payload is not None

