"""Single-user app — no auth required, return hardcoded user_id."""

from __future__ import annotations


DEFAULT_TRADER_ID = "default-trader"


def get_current_user_id() -> str:
    """Return the default trader ID (no auth validation needed).

    For future multi-user support: inject user_id from session/context here.
    """
    return DEFAULT_TRADER_ID
