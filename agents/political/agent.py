"""
Political Agent — narrative detection, speech analysis, constituency intelligence.
Shared by all political intelligence products.
"""
import json
from core.gateway import ai
from core.services import search_service, scraper_service, notification_service, translation_service
from core.observability import logger

NARRATIVE_PROMPT = """You are a political intelligence analyst specializing in Indian politics.
Analyze the content and return JSON:
{
  "narrative": "the main political narrative being pushed",
  "counter_narrative": "the opposing narrative",
  "key_politicians": ["politicians mentioned"],
  "parties": ["political parties involved"],
  "sentiment": "positive|negative|neutral|mixed",
  "target_audience": "who this message is aimed at",
  "emotional_triggers": ["anger|fear|pride|hope|outrage"],
  "factual_claims": ["verifiable claims made"],
  "propaganda_indicators": ["any propaganda techniques used"],
  "urgency": "critical|high|medium|low",
  "summary": "2-3 sentence plain English summary"
}"""

SPEECH_PROMPT = """You are a political speech analyst. Analyze this speech/statement.
Return JSON:
{
  "speaker": "name if identified",
  "occasion": "what event/context",
  "key_promises": ["promises made"],
  "key_attacks": ["attacks on opposition"],
  "policy_positions": ["policy stances mentioned"],
  "target_constituency": "who they are speaking to",
  "tone": "aggressive|defensive|conciliatory|inspiring|divisive",
  "hindi_summary": "50-word summary in Hindi",
  "english_summary": "50-word summary in English",
  "fact_check_needed": ["claims that need verification"],
  "quotable_lines": ["memorable quotes"]
}"""

CONSTITUENCY_PROMPT = """You are a constituency intelligence analyst.
Analyze local issues and sentiments for constituency-level political intelligence.
Return JSON:
{
  "constituency": "name if mentioned",
  "key_issues": ["local issues being discussed"],
  "dominant_sentiment": "positive|negative|neutral toward current rep",
  "popular_demands": ["what people are asking for"],
  "emerging_trends": ["new issues gaining traction"],
  "influencers": ["local leaders or voices mentioned"],
  "risk_level": "critical|high|medium|low for current political party",
  "opportunity": "what political opportunity exists here",
  "summary": "briefing for a politician"
}"""


class PoliticalAgent:
    def __init__(self, product_type: str, user_id: str, config: dict):
        self.product_type = product_type
        self.user_id = user_id
        self.constituency: str = config.get("constituency", "")
        self.keywords: list[str] = config.get("keywords", [])
        self.politicians: list[str] = config.get("politicians", [])
        self.delivery: dict = config.get("delivery", {})
        self.language: str = config.get("language", "en")

    async def run(self) -> dict:
        data = await self._collect()
        if not data:
            return {"items": [], "report": "No political data found."}

        if self.product_type == "speech_summarizer":
            return await self._analyze_speeches(data)
        elif self.product_type == "constituency":
            return await self._analyze_constituency(data)
        elif self.product_type == "narrative":
            return await self._analyze_narratives(data)
        elif self.product_type == "election":
            return await self._election_monitor(data)
        else:
            return await self._analyze_narratives(data)

    async def _collect(self) -> list[dict]:
        items = []
        search_queries = self.keywords + self.politicians + ([self.constituency] if self.constituency else [])

        for query in search_queries[:3]:
            news = await search_service.news(f"{query} politics India")
            hindi_news = await search_service.hindi_news(query)
            items.extend(news + hindi_news)

        # Reddit political subreddits
        for sub in ["india", "IndiaSpeaks", "unitedstatesofindia"]:
            if self.keywords:
                posts = await search_service.reddit(sub, " ".join(self.keywords[:2]))
                items.extend(posts[:5])

        return items[:25]

    async def _analyze_narratives(self, items: list[dict]) -> dict:
        import asyncio
        tasks = [self._analyze_one(item, NARRATIVE_PROMPT) for item in items[:10]]
        analyzed = await asyncio.gather(*tasks)

        # Generate overall narrative report
        all_narratives = [a.get("narrative", "") for a in analyzed if a.get("narrative")]
        report = await self._synthesize_report(analyzed, "narrative_tracker")

        await self._deliver(report)
        return {"items": analyzed, "report": report, "narratives": all_narratives}

    async def _analyze_speeches(self, items: list[dict]) -> dict:
        import asyncio
        tasks = [self._analyze_one(item, SPEECH_PROMPT) for item in items[:10]]
        analyzed = await asyncio.gather(*tasks)
        report = await self._synthesize_report(analyzed, "speech_summarizer")
        await self._deliver(report)
        return {"speeches": analyzed, "report": report}

    async def _analyze_constituency(self, items: list[dict]) -> dict:
        # Filter for constituency-specific content
        if self.constituency:
            items = [i for i in items if self.constituency.lower() in (i.get("title","") + i.get("snippet","")).lower()]

        import asyncio
        tasks = [self._analyze_one(item, CONSTITUENCY_PROMPT) for item in items[:10]]
        analyzed = await asyncio.gather(*tasks)
        report = await self._synthesize_report(analyzed, "constituency")
        await self._deliver(report)
        return {"constituency_data": analyzed, "report": report}

    async def _election_monitor(self, items: list[dict]) -> dict:
        analyzed = []
        for item in items[:15]:
            result = await self._analyze_one(item, NARRATIVE_PROMPT)
            analyzed.append(result)
        report = await self._synthesize_report(analyzed, "election_monitor")
        await self._deliver(report)
        return {"election_data": analyzed, "report": report}

    async def _analyze_one(self, item: dict, prompt: str) -> dict:
        text = f"Title: {item.get('title','')}\n\nContent: {item.get('snippet', item.get('text',''))[:2000]}"
        resp = await ai.complete(
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            task="analyze",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="political",
        )
        try:
            return {**item, **json.loads(resp["content"])}
        except Exception:
            return {**item, "summary": resp["content"][:300]}

    async def _synthesize_report(self, items: list[dict], report_type: str) -> str:
        summaries = "\n".join([f"- {i.get('summary', i.get('english_summary', ''))[:200]}" for i in items[:10]])
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": f"You are a political intelligence briefer. Create a {report_type} briefing from these data points. Be factual, concise, and insightful. Under 300 words."},
                {"role": "user", "content": summaries},
            ],
            task="summarize",
            user_id=self.user_id,
            bot_category="political",
        )
        # Translate if needed
        if self.language != "en":
            return await translation_service.summarize_in_language(resp["content"], self.language)
        return resp["content"]

    async def _deliver(self, report: str) -> None:
        tg = self.delivery.get("telegram_chat_id")
        if tg:
            label = self.product_type.replace("_", " ").title()
            await notification_service.telegram(tg, f"🗳️ *{label} Report*\n\n{report[:2000]}")
