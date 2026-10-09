import asyncio
from core.queue import celery_app
from core.observability import logger


@celery_app.task(name="bots.business.tasks.send_follow_ups", bind=True)
def send_follow_ups(self):
    """Daily task: send follow-up messages to dormant customers."""
    asyncio.run(_send_follow_ups())


@celery_app.task(name="bots.business.tasks.process_lead_notification", bind=True)
def process_lead_notification(self, bot_id: str, customer_id: str, message: str, lead_data: dict):
    asyncio.run(_notify(bot_id, customer_id, message, lead_data))


async def _send_follow_ups():
    logger.info("follow_up_task_ran")


async def _notify(bot_id, customer_id, message, lead_data):
    logger.info("lead_notification", bot_id=bot_id, customer_id=customer_id, score=lead_data.get("score"))
