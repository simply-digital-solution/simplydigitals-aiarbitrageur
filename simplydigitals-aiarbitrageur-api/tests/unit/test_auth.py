"""Tests for authentication — single-user, no JWT."""

from __future__ import annotations


def test_single_user_auth() -> None:
    """Verify auth is single-user with no JWT required."""
    from app.modules.auth.dependencies import get_current_user_id, DEFAULT_TRADER_ID

    # Test that get_current_user_id returns hardcoded value
    user_id = get_current_user_id()
    assert user_id == "default-trader", f"Expected 'default-trader', got '{user_id}'"
    assert DEFAULT_TRADER_ID == "default-trader"


def test_no_jwt_bearer_scheme() -> None:
    """Verify JWT bearer scheme has been removed."""
    from app.modules.auth import dependencies
    
    # Should not have HTTPBearer or JWTError
    assert not hasattr(dependencies, "HTTPBearer"), "HTTPBearer should not be present"
    assert hasattr(dependencies, "get_current_user_id")
