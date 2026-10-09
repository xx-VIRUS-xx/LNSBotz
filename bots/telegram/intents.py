"""Intent-specific handlers for the Telegram bot."""
from core.gateway import ai
from core.tools import web_fetch
from .prompts import SYSTEM_PROMPT


INTENT_SYSTEM_PROMPTS = {
    "research": "You are a research assistant. Give 5 key facts, explain clearly, cite sources where possible. Under 300 words.",
    "summarize": "You are a summarizer. Give: TL;DR (1 sentence), Key Points (5 bullets), Takeaway (1 line). Be ruthlessly concise.",
    "translate": "You are a translator. Translate the text as requested. Output ONLY the translation, nothing else.",
    "generate": "You are a content creator. Generate exactly what is asked. High quality, ready to use.",
    "calculate": "You are a calculator/analyst. Show the calculation steps clearly, then give the final answer.",
    "analyze": "You are an analyst. Break down the content, identify patterns, give structured insights.",
    "chat": SYSTEM_PROMPT,
}


async def handle_intent(
    intent: str,
    user_text: str,
    context_messages: list[dict],
    user_id: str,
) -> str:
    system = INTENT_SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPT)

    # For research intent, optionally enrich with web fetch
    enrichment = ""
    if intent == "research" and len(user_text) > 10:
        try:
            # Use DuckDuckGo instant answer API for basic enrichment
            import httpx, urllib.parse
            q = urllib.parse.quote(user_text[:100])
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1",
                    headers={"User-Agent": "BotEcosystem/1.0"},
                )
            data = resp.json()
            abstract = data.get("AbstractText", "")
            if abstract:
                enrichment = f"\n\n[Web context: {abstract[:500]}]"
        except Exception:
            pass

    resp = await ai.complete(
        messages=[
            {"role": "system", "content": system},
            *context_messages,
            {"role": "user", "content": user_text + enrichment},
        ],
        task=intent if intent != "chat" else "chat",
        user_id=user_id,
        bot_category="telegram",
    )
    return resp["content"]
