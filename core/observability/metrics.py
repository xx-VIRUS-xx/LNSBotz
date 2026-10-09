import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Callable
from core.observability.logger import get_logger
from core.cache import Cache

logger = get_logger("metrics")
_metrics_cache = Cache(prefix="metrics", ttl=86400)


async def track_usage(
    user_id: str,
    operation: str,
    bot_category: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    model: str = "",
    cost_usd: float = 0.0,
) -> None:
    """Fire-and-forget usage tracking to Redis (flushed to DB by Celery beat)."""
    key = f"{user_id}:{bot_category}:{operation}"
    await _metrics_cache.increment(f"usage:requests:{key}")
    await _metrics_cache.increment(f"usage:tokens_in:{key}", tokens_input)
    await _metrics_cache.increment(f"usage:tokens_out:{key}", tokens_output)
    logger.info(
        "usage_tracked",
        user_id=user_id,
        operation=operation,
        bot_category=bot_category,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        model=model,
        cost_usd=round(cost_usd, 6),
    )


@asynccontextmanager
async def timed_operation(name: str, user_id: str = "", **log_kwargs):
    """Context manager that logs duration of any async block."""
    start = time.perf_counter()
    try:
        yield
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error("operation_failed", name=name, user_id=user_id, duration_ms=duration_ms, error=str(e), **log_kwargs)
        raise
    else:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("operation_complete", name=name, user_id=user_id, duration_ms=duration_ms, **log_kwargs)
