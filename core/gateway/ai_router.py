"""
AI Gateway — Gemini-first, OpenAI optional fallback.
  - automatic fallback between Gemini models
  - response caching
  - cost tracking
  - structured output support
"""
import hashlib
import json
from typing import Any, AsyncIterator
import google.generativeai as genai
from core.config import settings
from core.cache import Cache
from core.observability import logger, track_usage

# Model cost table (USD per 1K tokens)
MODEL_COSTS = {
    "gemini-2.5-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-2.5-flash-lite": {"input": 0.000075, "output": 0.0003},
    "gemini-flash-latest": {"input": 0.0001, "output": 0.0004},
}

# gemini-2.5-flash for quality tasks, gemini-2.5-flash-lite for cheap/fast tasks
TASK_MODEL_MAP = {
    "summarize": "gemini-2.5-flash-lite",
    "classify": "gemini-2.5-flash-lite",
    "translate": "gemini-2.5-flash-lite",
    "extract": "gemini-2.5-flash-lite",
    "analyze": "gemini-2.5-flash",
    "generate": "gemini-2.5-flash",
    "chat": "gemini-2.5-flash-lite",
    "research": "gemini-2.5-flash",
    "plan": "gemini-2.5-flash",
}

_response_cache = Cache(prefix="ai_resp", ttl=3600)


class AIGateway:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is required")
        genai.configure(api_key=settings.GEMINI_API_KEY)

    def _select_model(self, task: str, force_model: str | None = None) -> str:
        if force_model:
            return force_model
        return TASK_MODEL_MAP.get(task, settings.DEFAULT_MODEL)

    def _cache_key(self, model: str, messages: list, **kwargs) -> str:
        payload = json.dumps({"model": model, "messages": messages, **kwargs}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _calc_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        costs = MODEL_COSTS.get(model, {"input": 0.002, "output": 0.002})
        return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1000

    async def complete(
        self,
        messages: list[dict],
        task: str = "chat",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: dict | None = None,
        use_cache: bool = True,
        user_id: str = "system",
        bot_category: str = "core",
    ) -> dict:
        """
        Returns: {
            "content": str,
            "model": str,
            "input_tokens": int,
            "output_tokens": int,
            "cost_usd": float,
            "cached": bool,
        }
        """
        selected_model = self._select_model(task, model)

        if use_cache:
            cache_key = self._cache_key(selected_model, messages, temperature=temperature)
            cached = await _response_cache.get(cache_key)
            if cached:
                logger.info("ai_cache_hit", model=selected_model, task=task)
                cached["cached"] = True
                return cached

        try:
            result = await self._call_model(selected_model, messages, temperature, max_tokens, response_format)
        except Exception as primary_err:
            logger.warning("ai_primary_failed", model=selected_model, error=str(primary_err))
            fallback = settings.FALLBACK_MODEL
            try:
                result = await self._call_model(fallback, messages, temperature, max_tokens, response_format)
                result["fallback"] = True
                selected_model = fallback
            except Exception as fallback_err:
                logger.error("ai_fallback_failed", model=fallback, error=str(fallback_err))
                raise

        result["cost_usd"] = self._calc_cost(selected_model, result["input_tokens"], result["output_tokens"])
        result["cached"] = False

        if use_cache:
            await _response_cache.set(cache_key, result)

        await track_usage(
            user_id=user_id,
            operation=task,
            bot_category=bot_category,
            tokens_input=result["input_tokens"],
            tokens_output=result["output_tokens"],
            model=selected_model,
            cost_usd=result["cost_usd"],
        )

        return result

    async def _call_model(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> dict:
        if model.startswith("gemini"):
            return await self._call_gemini(model, messages, temperature, max_tokens, response_format)
        raise ValueError(f"Unknown model provider for: {model}")

    async def _call_gemini(self, model, messages, temperature, max_tokens, response_format=None) -> dict:
        # Convert OpenAI message format to Gemini
        history = []
        system_prompt = ""
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            elif m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})

        gen_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        # JSON mode: instruct Gemini to return valid JSON
        if response_format and response_format.get("type") == "json_object":
            gen_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            )

        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt or None,
            generation_config=gen_config,
        )
        last_user = history.pop() if history and history[-1]["role"] == "user" else {"parts": [""]}
        chat = gemini_model.start_chat(history=history)
        resp = await chat.send_message_async(last_user["parts"][0])

        input_est = sum(len(m.get("content", "")) for m in messages) // 4
        output_est = len(resp.text) // 4
        return {
            "content": resp.text,
            "model": model,
            "input_tokens": input_est,
            "output_tokens": output_est,
        }

    async def stream(
        self,
        messages: list[dict],
        task: str = "chat",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Streaming response via Gemini."""
        selected_model = self._select_model(task, model)
        history, system_prompt = [], ""
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            elif m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})

        gemini_model = genai.GenerativeModel(
            model_name=selected_model,
            system_instruction=system_prompt or None,
            generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens),
        )
        last_user = history.pop() if history and history[-1]["role"] == "user" else {"parts": [""]}
        chat = gemini_model.start_chat(history=history)
        async for chunk in await chat.send_message_async(last_user["parts"][0], stream=True):
            if chunk.text:
                yield chunk.text


# Singleton used across the app
ai = AIGateway()
