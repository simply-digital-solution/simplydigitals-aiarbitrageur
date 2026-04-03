"""Trigger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import get_current_user_id
from app.modules.triggers.schemas import TriggerCreate, TriggerRead, TriggerUpdate
from app.modules.triggers.service import TriggerService
from app.shared.database import get_db

router = APIRouter(prefix="/triggers", tags=["triggers"])


@router.get("", response_model=list[TriggerRead])
async def list_triggers(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[TriggerRead]:
    triggers = await TriggerService(db).list_triggers(user_id)
    return [TriggerRead.model_validate(t) for t in triggers]


@router.post("", response_model=TriggerRead, status_code=201)
async def create_trigger(
    req: TriggerCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TriggerRead:
    trigger = await TriggerService(db).create(req, user_id)
    return TriggerRead.model_validate(trigger)


@router.patch("/{trigger_id}", response_model=TriggerRead)
async def update_trigger(
    trigger_id: str,
    req: TriggerUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TriggerRead:
    trigger = await TriggerService(db).update(trigger_id, req, user_id)
    return TriggerRead.model_validate(trigger)


@router.delete("/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    await TriggerService(db).delete(trigger_id, user_id)
