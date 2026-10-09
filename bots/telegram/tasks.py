import asyncio
from core.queue import celery_app
from core.observability import logger


@celery_app.task(name="bots.telegram.tasks.send_broadcast", bind=True)
def send_broadcast(self, bot_id: str, chat_ids: list[str], message: str):
    asyncio.run(_broadcast(bot_id, chat_ids, message))


async def _broadcast(bot_id: str, chat_ids: list[str], message: str):
    from core.tools import telegram_send
    for chat_id in chat_ids:
        try:
            await telegram_send(chat_id, message)
        except Exception as e:
            logger.warning("broadcast_failed", chat_id=chat_id, error=str(e))
