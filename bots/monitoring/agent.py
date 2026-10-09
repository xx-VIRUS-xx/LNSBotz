"""
AI Monitoring Bot — the core agent.

Flow: fetch sources → filter by keywords → AI analyze → score urgency/sentiment
      → deduplicate → store alerts → deliver via Telegram/email
"""
from datetime import datetime, timezone
from core.gateway import ai
from core.tools import rss_fetch, reddit_fetch, web_fetch, telegram_send, email_send
from core.observability import logger
from .prompts import ANALYZE_PROMPT, DIGEST_PROMPT


class MonitoringAgent:
    def __init__(self, bot_id: str, user_id: str, config: dict):
        self.bot_id = bot_id
        self.user_id = user_id
        self.keywords: list[str] = config.get("keywords", [])
        self.delivery: dict = config.get("delivery", {})
        self.sources: list[dict] = config.get("sources", [])

    async def run(self) -> list[dict]:
        """Main execution loop. Returns list of new alerts."""
        all_items = []
        for source in self.sources:
            try:
                items = await self._fetch_source(source)
                all_items.extend(items)
            except Exception as e:
                logger.warning("source_fetch_failed", source=source, error=str(e))

        if not all_items:
            return []

        filtered = self._filter_by_keywords(all_items)
        if not filtered:
            return []

        analyzed = await self._analyze_items(filtered[:15])  # cap per run
        await self._deliver(analyzed)
        return analyzed

    async def _fetch_source(self, source: dict) -> list[dict]:
        stype = source.get("type")
        url = source.get("url", "")
        if stype == "rss":
            entries = await rss_fetch(url)
            return [{"source_type": "rss", "title": e["title"], "text": e["summary"],
                     "url": e["link"], "published": e["published"]} for e in entries]
        elif stype == "reddit":
            subreddit = source.get("subreddit", url.split("/r/")[-1].split("/")[0])
            posts = await reddit_fetch(subreddit, limit=25)
            return [{"source_type": "reddit", "title": p["title"], "text": p["selftext"],
                     "url": p["permalink"], "score": p["score"]} for p in posts]
        elif stype == "webpage":
            html = await web_fetch(url)
            return [{"source_type": "webpage", "title": url, "text": html[:3000], "url": url}]
        return []

    def _filter_by_keywords(self, items: list[dict]) -> list[dict]:
        if not self.keywords:
            return items
        filtered = []
        kws = [k.lower() for k in self.keywords]
        for item in items:
            haystack = (item.get("title", "") + " " + item.get("text", "")).lower()
            if any(kw in haystack for kw in kws):
                filtered.append(item)
        return filtered

    async def _analyze_items(self, items: list[dict]) -> list[dict]:
        results = []
        for item in items:
            text = f"Title: {item.get('title', '')}\n\nContent: {item.get('text', '')[:1500]}"
            resp = await ai.complete(
                messages=[
                    {"role": "system", "content": ANALYZE_PROMPT},
                    {"role": "user", "content": text},
                ],
                task="analyze",
                response_format={"type": "json_object"},
                user_id=self.user_id,
                bot_category="monitoring",
            )
            try:
                import json
                analysis = json.loads(resp["content"])
            except Exception:
                analysis = {"summary": resp["content"], "sentiment": "neutral", "urgency": "low"}

            results.append({
                **item,
                "summary": analysis.get("summary", ""),
                "sentiment": analysis.get("sentiment", "neutral"),
                "urgency": analysis.get("urgency", "low"),
                "topics": analysis.get("topics", []),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            })
        return results

    async def _deliver(self, alerts: list[dict]) -> None:
        if not alerts:
            return
        high_urgency = [a for a in alerts if a.get("urgency") in ("high", "critical")]
        delivery_items = high_urgency if high_urgency else alerts[:3]

        # Telegram delivery
        if self.delivery.get("telegram_chat_id"):
            text = self._format_telegram(delivery_items)
            await telegram_send(self.delivery["telegram_chat_id"], text)

        # Email delivery
        if self.delivery.get("email"):
            body = self._format_email(delivery_items)
            await email_send(
                to=self.delivery["email"],
                subject=f"[Alert] {len(delivery_items)} new monitored items",
                body=body,
                html=True,
            )

    def _format_telegram(self, alerts: list[dict]) -> str:
        lines = ["*🔔 Monitoring Alert*\n"]
        for a in alerts[:5]:
            urgency_emoji = {"critical": "🚨", "high": "⚠️", "medium": "ℹ️", "low": "📌"}.get(a.get("urgency", "low"), "📌")
            lines.append(f"{urgency_emoji} *{a.get('title', 'No title')[:80]}*")
            lines.append(f"_{a.get('summary', '')[:200]}_")
            lines.append(f"Sentiment: {a.get('sentiment', 'N/A')} | Urgency: {a.get('urgency', 'N/A')}")
            if a.get("url"):
                lines.append(f"[Read more]({a['url']})")
            lines.append("")
        return "\n".join(lines)[:4000]

    def _format_email(self, alerts: list[dict]) -> str:
        rows = ""
        for a in alerts:
            rows += f"""
            <tr>
                <td><a href="{a.get('url','#')}">{a.get('title','')[:100]}</a></td>
                <td>{a.get('summary','')[:200]}</td>
                <td>{a.get('sentiment','')}</td>
                <td>{a.get('urgency','')}</td>
            </tr>"""
        return f"""
        <html><body>
        <h2>Monitoring Digest</h2>
        <table border="1" cellpadding="6" style="border-collapse:collapse;width:100%">
            <tr><th>Title</th><th>Summary</th><th>Sentiment</th><th>Urgency</th></tr>
            {rows}
        </table>
        </body></html>"""


async def generate_daily_digest(bot_id: str, user_id: str, alerts: list[dict], delivery: dict) -> str:
    """Synthesize all alerts from the day into a single digest narrative."""
    if not alerts:
        return "No significant activity today."

    summaries = "\n".join([f"- {a.get('title', '')}: {a.get('summary', '')}" for a in alerts[:20]])
    resp = await ai.complete(
        messages=[
            {"role": "system", "content": DIGEST_PROMPT},
            {"role": "user", "content": f"Today's monitored items:\n{summaries}"},
        ],
        task="summarize",
        user_id=user_id,
        bot_category="monitoring",
    )
    return resp["content"]
