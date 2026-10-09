"""Monitoring Bot REST API routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.db import get_db, BotInstance, BotCategory, User
from core.auth import get_current_user_flexible, require_plan
from core.db.models import PlanTier
from .tasks import run_single_monitor

router = APIRouter(prefix="/monitoring", tags=["Monitoring Bots"])


class SourceConfig(BaseModel):
    type: Literal["rss", "reddit", "webpage"]
    url: str
    subreddit: str | None = None


class DeliveryConfig(BaseModel):
    telegram_chat_id: str | None = None
    email: str | None = None


class CreateMonitorRequest(BaseModel):
    name: str
    keywords: list[str]
    sources: list[SourceConfig]
    delivery: DeliveryConfig


@router.post("/", summary="Create a monitoring bot")
async def create_monitor(
    req: CreateMonitorRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    bot = BotInstance(
        user_id=user.id,
        name=req.name,
        category=BotCategory.MONITORING,
        config={
            "keywords": req.keywords,
            "sources": [s.model_dump() for s in req.sources],
            "delivery": req.delivery.model_dump(exclude_none=True),
        },
    )
    db.add(bot)
    await db.flush()
    return {"id": str(bot.id), "name": bot.name, "status": "created"}


@router.get("/", summary="List my monitoring bots")
async def list_monitors(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(
        select(BotInstance).where(
            BotInstance.user_id == user.id,
            BotInstance.category == BotCategory.MONITORING,
        )
    )
    bots = result.scalars().all()
    return [{"id": str(b.id), "name": b.name, "active": b.is_active, "config": b.config} for b in bots]


@router.post("/{bot_id}/run", summary="Trigger a manual run")
async def trigger_run(
    bot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(
        select(BotInstance).where(BotInstance.id == bot_id, BotInstance.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    task = run_single_monitor.delay(str(bot.id), str(user.id), bot.config or {})
    return {"task_id": task.id, "status": "queued"}


@router.delete("/{bot_id}", summary="Delete a monitoring bot")
async def delete_monitor(
    bot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(
        select(BotInstance).where(BotInstance.id == bot_id, BotInstance.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")
    await db.delete(bot)
    return {"status": "deleted"}
