"""
Property Agent — listing analysis, valuation, ROI, fraud detection.
"""
import json
from core.gateway import ai
from core.services import search_service, scraper_service, document_service
from core.observability import logger

LISTING_PROMPT = """You are a real estate expert in India. Analyze this property listing.
Return JSON:
{
  "property_type": "apartment|villa|plot|commercial|other",
  "location": "city/area",
  "size_sqft": 0,
  "price": 0,
  "price_per_sqft": 0,
  "bedrooms": 0,
  "key_features": ["feature1"],
  "valuation_assessment": "overpriced|fair|underpriced",
  "estimated_market_price": 0,
  "price_deviation_pct": 0,
  "roi_estimate_pct": 0,
  "rental_yield_pct": 0,
  "red_flags": ["fraud indicators or suspicious elements"],
  "positives": ["good points"],
  "location_score": "1-10",
  "investment_recommendation": "buy|avoid|negotiate|watch",
  "summary": "2-3 sentence analysis for a buyer"
}"""

MARKET_PROMPT = """You are a real estate market analyst for India.
Analyze current market trends for this location/type.
Return JSON:
{
  "location": "...",
  "market_trend": "rising|falling|stable",
  "avg_price_per_sqft": 0,
  "price_change_6m_pct": 0,
  "demand_level": "high|medium|low",
  "top_localities": ["best areas to invest"],
  "avoid_areas": ["areas to avoid"],
  "best_property_types": ["what's in demand"],
  "upcoming_infrastructure": ["projects that will boost prices"],
  "summary": "market briefing"
}"""


class PropertyAgent:
    def __init__(self, user_id: str, config: dict | None = None):
        self.user_id = user_id
        self.config = config or {}

    async def analyze_listing(self, listing_text: str | None = None,
                               listing_url: str | None = None,
                               document_bytes: bytes | None = None) -> dict:
        """Analyze a property listing from text, URL, or document."""
        if listing_url:
            listing_text = await scraper_service.fetch_text(listing_url, max_chars=5000)
        elif document_bytes:
            listing_text = await document_service.extract_pdf(document_bytes)

        if not listing_text:
            return {"error": "No property data provided"}

        resp = await ai.complete(
            messages=[
                {"role": "system", "content": LISTING_PROMPT},
                {"role": "user", "content": f"Property listing:\n\n{listing_text[:4000]}"},
            ],
            task="analyze",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="property",
        )
        try:
            result = json.loads(resp["content"])
        except Exception:
            result = {"summary": resp["content"]}

        # Enrich with market data
        location = result.get("location", "")
        if location:
            market = await self.get_market_intelligence(location, result.get("property_type", ""))
            result["market_context"] = market

        return result

    async def get_market_intelligence(self, location: str, property_type: str = "") -> dict:
        """Get real estate market intelligence for a location."""
        news = await search_service.news(f"real estate property prices {location} {property_type} 2025")
        context = "\n".join([f"- {n['title']}: {n['snippet'][:200]}" for n in news[:5]])

        resp = await ai.complete(
            messages=[
                {"role": "system", "content": MARKET_PROMPT},
                {"role": "user", "content": f"Location: {location}\nProperty type: {property_type}\n\nRecent news:\n{context}"},
            ],
            task="analyze",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="property",
        )
        try:
            return json.loads(resp["content"])
        except Exception:
            return {"summary": resp["content"][:300]}

    async def detect_fraud_indicators(self, listing_text: str) -> list[str]:
        """Check for common real estate fraud patterns."""
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": "You are a real estate fraud detection expert in India. List any fraud indicators or red flags in this listing. Return a JSON array of strings. If none found, return []. Common frauds: benami property, fake ownership, inflated prices, missing RERA registration, unclear title."},
                {"role": "user", "content": listing_text[:3000]},
            ],
            task="classify",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="property",
        )
        try:
            data = json.loads(resp["content"])
            return data if isinstance(data, list) else data.get("flags", data.get("red_flags", []))
        except Exception:
            return []
