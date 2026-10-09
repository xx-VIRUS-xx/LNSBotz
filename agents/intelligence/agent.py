"""
Intelligence Agent — shared by ALL monitoring products.
Trend detection, sentiment, anomaly, clustering, alerts, reports.
Products are just configured instances of this agent.
"""
import json
from core.gateway import ai
from core.services import search_service, scraper_service, notification_service
from core.observability import logger


ANALYZE_PROMPT = """You are an intelligence analyst. Analyze the content and return JSON:
{
  "summary": "2-3 sentence summary",
  "sentiment": "positive|negative|neutral|mixed",
  "urgency": "critical|high|medium|low",
  "topics": ["topic1", "topic2"],
  "entities": ["person/org/place mentioned"],
  "narrative": "what story/narrative is being pushed",
  "anomaly": true/false,
  "anomaly_reason": "why this is anomalous (if true)"
}"""

CLUSTER_PROMPT = """Group these items by theme. Return JSON:
{
  "clusters": [
    {"theme": "theme name", "items": [0, 2, 5], "summary": "what this cluster is about"}
  ]
}"""

REPORT_PROMPT = """You are an intelligence briefer. Create a structured report from these data points.
Format:
## Executive Summary (2-3 sentences)
## Key Findings (5 bullets)
## Sentiment Overview
## Trending Topics
## Anomalies / Alerts
## Recommended Actions
Keep it under 400 words. Factual, no fluff."""


class IntelligenceAgent:
    def __init__(self, product_type: str, user_id: str, config: dict):
        self.product_type = product_type  # competitor, political, reddit, tender, stock, job, etc.
        self.user_id = user_id
        self.keywords: list[str] = config.get("keywords", [])
        self.sources: list[dict] = config.get("sources", [])
        self.delivery: dict = config.get("delivery", {})
        self.language: str = config.get("language", "en")

    async def run(self) -> dict:
        """Main execution. Returns {items, clusters, report, alerts}."""
        raw_items = await self._collect()
        if not raw_items:
            return {"items": [], "clusters": [], "report": "No data found.", "alerts": []}

        analyzed = await self._analyze_all(raw_items[:20])
        clusters = await self._cluster(analyzed)
        alerts = [i for i in analyzed if i.get("urgency") in ("critical", "high")]
        report = await self._generate_report(analyzed)

        await self._deliver(alerts, report)
        return {"items": analyzed, "clusters": clusters, "report": report, "alerts": alerts}

    async def _collect(self) -> list[dict]:
        items = []
        for source in self.sources:
            stype = source.get("type")
            try:
                if stype == "news":
                    results = await search_service.news(source.get("query", " ".join(self.keywords)))
                    items.extend(results)
                elif stype == "hindi_news":
                    results = await search_service.hindi_news(source.get("query", " ".join(self.keywords)))
                    items.extend(results)
                elif stype == "reddit":
                    results = await search_service.reddit(source.get("subreddit", "india"), " ".join(self.keywords))
                    items.extend(results)
                elif stype == "rss":
                    results = await scraper_service.fetch_rss(source.get("url", ""))
                    items.extend(results)
                elif stype == "web":
                    text = await scraper_service.fetch_text(source.get("url", ""))
                    if text:
                        items.append({"title": source.get("url", ""), "snippet": text[:500], "url": source.get("url", "")})
                elif stype == "twitter_trends":
                    results = await search_service.twitter_trends()
                    items.extend(results)
                elif stype == "jobs":
                    results = await search_service.jobs(" ".join(self.keywords))
                    items.extend(results)
                elif stype == "tender":
                    results = await search_service.government_tenders(" ".join(self.keywords))
                    items.extend(results)
            except Exception as e:
                logger.warning("intel_collect_failed", source=stype, error=str(e))

        # Keyword filter
        if self.keywords:
            kws = [k.lower() for k in self.keywords]
            items = [i for i in items if any(kw in (i.get("title","") + i.get("snippet","") + i.get("text","")).lower() for kw in kws)]

        return items

    async def _analyze_all(self, items: list[dict]) -> list[dict]:
        import asyncio
        tasks = [self._analyze_one(item) for item in items]
        return await asyncio.gather(*tasks)

    async def _analyze_one(self, item: dict) -> dict:
        text = f"Title: {item.get('title','')}\n\nContent: {item.get('snippet', item.get('text',''))[:1500]}"
        resp = await ai.complete(
            messages=[{"role": "system", "content": ANALYZE_PROMPT}, {"role": "user", "content": text}],
            task="analyze",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="intelligence",
        )
        try:
            analysis = json.loads(resp["content"])
        except Exception:
            analysis = {"summary": resp["content"][:300], "sentiment": "neutral", "urgency": "low"}
        return {**item, **analysis}

    async def _cluster(self, items: list[dict]) -> list[dict]:
        if len(items) < 3:
            return []
        titles = "\n".join([f"[{i}] {item.get('title','')[:80]}" for i, item in enumerate(items)])
        resp = await ai.complete(
            messages=[{"role": "system", "content": CLUSTER_PROMPT}, {"role": "user", "content": titles}],
            task="classify",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="intelligence",
        )
        try:
            return json.loads(resp["content"]).get("clusters", [])
        except Exception:
            return []

    async def _generate_report(self, items: list[dict]) -> str:
        summaries = "\n".join([f"- [{item.get('sentiment','?')}][{item.get('urgency','?')}] {item.get('title','')}: {item.get('summary','')[:150]}" for item in items[:15]])
        resp = await ai.complete(
            messages=[{"role": "system", "content": REPORT_PROMPT}, {"role": "user", "content": summaries}],
            task="summarize",
            user_id=self.user_id,
            bot_category="intelligence",
        )
        return resp["content"]

    async def _deliver(self, alerts: list[dict], report: str) -> None:
        tg = self.delivery.get("telegram_chat_id")
        if not tg:
            return
        if alerts:
            for alert in alerts[:3]:
                msg = notification_service.format_alert(
                    title=alert.get("title", ""),
                    summary=alert.get("summary", ""),
                    url=alert.get("url", ""),
                    urgency=alert.get("urgency", "medium"),
                    sentiment=alert.get("sentiment", "neutral"),
                    tags=alert.get("topics", []),
                )
                await notification_service.telegram(tg, msg)
        else:
            digest_items = [{"title": i.get("title",""), "summary": i.get("summary",""), "urgency": i.get("urgency","low")} for i in alerts or []]
            await notification_service.telegram(tg, f"📊 *{self.product_type.replace('_',' ').title()} Update*\n\n{report[:2000]}")
