"""
Conversation memory for Telegram/WhatsApp bots.
Short-term: Redis (fast, per-session sliding window).
Long-term: PostgreSQL (persisted ConversationSession rows).
"""
import json
from typing import Any
from core.cache import get_redis
from core.config import settings

MAX_MESSAGES = 20  # keep last N messages in context window
SESSION_TTL = 86400 * 7  # 7 days


class SessionMemory:
    def __init__(self, bot_id: str, user_id: str, platform: str):
        self.bot_id = bot_id
        self.user_id = user_id
        self.platform = platform
        self._key = f"session:{platform}:{bot_id}:{user_id}"

    async def add_message(self, role: str, content: str, metadata: dict | None = None) -> None:
        r = await get_redis()
        message = {"role": role, "content": content, **({"meta": metadata} if metadata else {})}
        await r.rpush(self._key, json.dumps(message))
        await r.ltrim(self._key, -MAX_MESSAGES, -1)  # keep only last N
        await r.expire(self._key, SESSION_TTL)

    async def get_messages(self, limit: int = MAX_MESSAGES) -> list[dict]:
        r = await get_redis()
        raw = await r.lrange(self._key, -limit, -1)
        return [json.loads(m) for m in raw]

    async def get_context_messages(self) -> list[dict]:
        """Return messages in OpenAI format for use in AI calls."""
        msgs = await self.get_messages()
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    async def clear(self) -> None:
        r = await get_redis()
        await r.delete(self._key)

    async def set_metadata(self, key: str, value: Any) -> None:
        r = await get_redis()
        meta_key = f"{self._key}:meta"
        await r.hset(meta_key, key, json.dumps(value))
        await r.expire(meta_key, SESSION_TTL)

    async def get_metadata(self, key: str) -> Any | None:
        r = await get_redis()
        meta_key = f"{self._key}:meta"
        val = await r.hget(meta_key, key)
        return json.loads(val) if val else None
