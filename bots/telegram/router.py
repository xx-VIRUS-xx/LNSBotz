"""Telegram webhook + management routes."""
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.db import get_db, BotInstance, BotCategory, User
from core.auth import get_current_user_flexible
from core.config import settings
from core.observability import logger
from .agent import TelegramAgent

router = APIRouter(prefix="/telegram", tags=["Telegram Bot"])

_agents: dict[str, TelegramAgent] = {}


def _get_agent(bot_id: str, token: str) -> TelegramAgent:
    if bot_id not in _agents:
        _agents[bot_id] = TelegramAgent(bot_id, token)
    return _agents[bot_id]


@router.post("/webhook/{bot_id}", include_in_schema=False)
async def telegram_webhook(
    bot_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receives Telegram updates for a specific bot instance."""
    result = await db.execute(
        select(BotInstance).where(
            BotInstance.id == bot_id,
            BotInstance.category == BotCategory.TELEGRAM,
            BotInstance.is_active == True,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    token = (bot.config or {}).get("telegram_token", settings.TELEGRAM_BOT_TOKEN)
    if not token:
        raise HTTPException(500, "No Telegram token configured")

    update = await request.json()
    agent = _get_agent(bot_id, token)

    # Process async (non-blocking)
    import asyncio
    asyncio.create_task(agent.handle_update(update))
    return {"ok": True}


class CreateTelegramBotRequest(BaseModel):
    name: str
    telegram_token: str
    system_prompt: str | None = None


@router.post("/", summary="Create a Telegram bot instance")
async def create_telegram_bot(
    req: CreateTelegramBotRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    bot = BotInstance(
        user_id=user.id,
        name=req.name,
        category=BotCategory.TELEGRAM,
        config={
            "telegram_token": req.telegram_token,
            "system_prompt": req.system_prompt,
        },
    )
    db.add(bot)
    await db.flush()

    bot_id = str(bot.id)
    webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}/api/v1/telegram/webhook/{bot_id}"

    # Register webhook with Telegram
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{req.telegram_token}/setWebhook",
            json={"url": webhook_url},
        )
    webhook_ok = resp.json().get("ok", False)

    return {
        "id": bot_id,
        "name": bot.name,
        "webhook_url": webhook_url,
        "webhook_registered": webhook_ok,
    }
