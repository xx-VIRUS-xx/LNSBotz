from celery import Celery
from celery.schedules import crontab
from core.config import settings

celery_app = Celery(
    "bot_ecosystem",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "bots.monitoring.tasks",
        "bots.content.tasks",
        "bots.telegram.tasks",
        "bots.business.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_max_retries=3,
    task_default_retry_delay=60,
    result_expires=86400,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# ── Scheduled Tasks (Beat) ────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "monitoring-run-every-15min": {
        "task": "bots.monitoring.tasks.run_all_monitors",
        "schedule": crontab(minute="*/15"),
    },
    "monitoring-daily-digest": {
        "task": "bots.monitoring.tasks.send_daily_digest",
        "schedule": crontab(hour=8, minute=0),  # 8 AM UTC daily
    },
    "content-check-queue": {
        "task": "bots.content.tasks.process_pending_jobs",
        "schedule": crontab(minute="*/5"),
    },
    "billing-usage-rollup": {
        "task": "core.queue.billing_tasks.rollup_usage",
        "schedule": crontab(hour=0, minute=0),  # midnight UTC
    },
}
