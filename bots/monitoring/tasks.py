"""Celery tasks for the Monitoring Bot — runs on schedule."""
import asyncio
from core.queue import celery_app
from core.observability import logger


@celery_app.task(
    name="bots.monitoring.tasks.run_all_monitors",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_all_monitors(self):
    """Runs every 15 minutes via beat schedule."""
    asyncio.run(_run_all_monitors_async())


@celery_app.task(name="bots.monitoring.tasks.run_single_monitor", bind=True, max_retries=3)
def run_single_monitor(self, bot_id: str, user_id: str, config: dict):
    asyncio.run(_run_single(bot_id, user_id, config))


@celery_app.task(name="bots.monitoring.tasks.send_daily_digest", bind=True)
def send_daily_digest(self):
    asyncio.run(_send_digests())


async def _run_all_monitors_async():
    from sqlalchemy import select
    from core.db import AsyncSessionLocal, BotInstance, BotCategory
    from .agent import MonitoringAgent

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BotInstance).where(
                BotInstance.category == BotCategory.MONITORING,
                BotInstance.is_active == True,
            )
        )
        bots = result.scalars().all()

    for bot in bots:
        try:
            agent = MonitoringAgent(str(bot.id), str(bot.user_id), bot.config or {})
            alerts = await agent.run()
            logger.info("monitor_ran", bot_id=str(bot.id), alerts_found=len(alerts))
        except Exception as e:
            logger.error("monitor_failed", bot_id=str(bot.id), error=str(e))


async def _run_single(bot_id: str, user_id: str, config: dict):
    from .agent import MonitoringAgent
    agent = MonitoringAgent(bot_id, user_id, config)
    return await agent.run()


async def _send_digests():
    from sqlalchemy import select
    from core.db import AsyncSessionLocal, BotInstance, BotCategory, MonitoredAlert
    from .agent import generate_daily_digest

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BotInstance).where(
                BotInstance.category == BotCategory.MONITORING,
                BotInstance.is_active == True,
            )
        )
        bots = result.scalars().all()

    for bot in bots:
        try:
            delivery = (bot.config or {}).get("delivery", {})
            digest = await generate_daily_digest(str(bot.id), str(bot.user_id), [], delivery)
            logger.info("digest_sent", bot_id=str(bot.id))
        except Exception as e:
            logger.error("digest_failed", bot_id=str(bot.id), error=str(e))
