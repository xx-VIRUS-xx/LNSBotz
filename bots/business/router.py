"""Local Business AI Agent REST API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.db import get_db, BotInstance, BotCategory, User
from core.auth import get_current_user_flexible
from .agent import BusinessAgent

router = APIRouter(prefix="/business", tags=["Business AI Agent"])

_agents: dict[str, BusinessAgent] = {}


def _get_or_create_agent(bot: BotInstance) -> BusinessAgent:
    key = str(bot.id)
    if key not in _agents:
        _agents[key] = BusinessAgent(key, str(bot.user_id), bot.config or {})
    return _agents[key]


class CreateBusinessBotRequest(BaseModel):
    name: str
    business_name: str
    business_type: Literal["clinic", "salon", "restaurant", "coaching", "real_estate", "retail", "service"]
    services: list[str]
    booking_url: str | None = None
    owner_contact: dict | None = None
    platform: Literal["telegram", "whatsapp"] = "telegram"


class IncomingMessageRequest(BaseModel):
    bot_id: str
    customer_id: str
    message: str
    channel: str = "telegram"


class CampaignRequest(BaseModel):
    bot_id: str
    campaign_type: Literal["promotional", "seasonal", "referral", "reactivation", "launch"]
    target_audience: str
    goal: str


@router.post("/", summary="Create a business AI bot")
async def create_business_bot(
    req: CreateBusinessBotRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    bot = BotInstance(
        user_id=user.id,
        name=req.name,
        category=BotCategory.BUSINESS,
        config={
            "business_name": req.business_name,
            "business_type": req.business_type,
            "services": req.services,
            "booking_url": req.booking_url,
            "owner_contact": req.owner_contact or {},
            "platform": req.platform,
        },
    )
    db.add(bot)
    await db.flush()
    return {"id": str(bot.id), "name": bot.name, "status": "created"}


@router.post("/message", summary="Send a message to the business agent")
async def send_message(
    req: IncomingMessageRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(
        select(BotInstance).where(
            BotInstance.id == req.bot_id,
            BotInstance.user_id == user.id,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    agent = _get_or_create_agent(bot)
    reply = await agent.handle_message(req.customer_id, req.message, req.channel)
    return {"reply": reply}


@router.post("/campaign", summary="Generate a marketing campaign")
async def generate_campaign(
    req: CampaignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(
        select(BotInstance).where(BotInstance.id == req.bot_id, BotInstance.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    agent = _get_or_create_agent(bot)
    campaign = await agent.generate_campaign(req.campaign_type, req.target_audience, req.goal)
    return campaign


@router.post("/webhook/{bot_id}", include_in_schema=False)
async def business_webhook(bot_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Receive WhatsApp/Telegram messages for a business bot."""
    result = await db.execute(
        select(BotInstance).where(
            BotInstance.id == bot_id,
            BotInstance.category == BotCategory.BUSINESS,
            BotInstance.is_active == True,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    body = await request.json()
    agent = _get_or_create_agent(bot)

    # Normalize incoming message from various platforms
    customer_id = body.get("from") or body.get("customer_id", "unknown")
    message = body.get("text") or body.get("message") or body.get("Body", "")
    platform = (bot.config or {}).get("platform", "telegram")

    if message:
        import asyncio
        asyncio.create_task(agent.handle_message(customer_id, message, platform))

    return {"ok": True}
