"""Tests for background scheduler and job execution."""

from __future__ import annotations


def test_scheduler_job_functions() -> None:
    """Verify all scheduler job functions are defined."""
    from app.shared.scheduler import (
        _job_fetch_intraday,
        _job_fetch_closing,
        _job_purge_intraday,
        _job_fetch_intraday_1min,
        _job_purge_intraday_1min,
        _job_sync_positions,
        _job_evaluate_triggers,
    )

    # All should be callable
    assert callable(_job_fetch_intraday)
    assert callable(_job_fetch_closing)
    assert callable(_job_purge_intraday)
    assert callable(_job_fetch_intraday_1min)
    assert callable(_job_purge_intraday_1min)
    assert callable(_job_sync_positions)
    assert callable(_job_evaluate_triggers)


def test_scheduler_actions_dict() -> None:
    """Verify ACTIONS dict has all job mappings."""
    from app.shared.scheduler import ACTIONS

    required_actions = [
        "fetch_intraday",
        "fetch_closing",
        "purge_intraday",
        "fetch_intraday_1min",
        "purge_intraday_1min",
        "sync_positions",
        "evaluate_triggers",
    ]

    for action in required_actions:
        assert action in ACTIONS, f"Missing action in ACTIONS dict: {action}"
        assert callable(ACTIONS[action]), f"Action {action} is not callable"


def test_1min_jobs_in_actions() -> None:
    """Verify 1-minute specific jobs are registered."""
    from app.shared.scheduler import ACTIONS

    assert "fetch_intraday_1min" in ACTIONS
    assert "purge_intraday_1min" in ACTIONS


def test_position_sync_job_in_actions() -> None:
    """Verify position sync job is registered."""
    from app.shared.scheduler import ACTIONS

    assert "sync_positions" in ACTIONS


def test_trigger_evaluation_job_in_actions() -> None:
    """Verify trigger evaluation job is registered."""
    from app.shared.scheduler import ACTIONS

    assert "evaluate_triggers" in ACTIONS
