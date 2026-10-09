import asyncio
from core.queue import celery_app
from core.observability import logger


@celery_app.task(name="bots.content.tasks.transform_content", bind=True, max_retries=2)
def transform_content(self, user_id: str, input_type: str, source: str, output_format: str, options: dict = None):
    return asyncio.run(_transform(user_id, input_type, source, output_format, options or {}))


@celery_app.task(name="bots.content.tasks.process_pending_jobs", bind=True)
def process_pending_jobs(self):
    """Process any queued transformation jobs."""
    asyncio.run(_process_pending())


async def _transform(user_id, input_type, source, output_format, options):
    from .agent import ContentAgent
    agent = ContentAgent(user_id=user_id)
    return await agent.transform(input_type, source, output_format, options)


async def _process_pending():
    logger.info("content_jobs_check_ran")
