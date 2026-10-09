"""
Shared Scraping Service — websites, news portals, government portals.
Uses httpx for simple pages, falls back to structured extraction via AI.
"""
import httpx
import re
from core.observability import logger


class ScraperService:

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    }

    async def fetch_text(self, url: str, max_chars: int = 8000) -> str:
        """Fetch URL and return clean text."""
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=self.HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            return self._clean_html(resp.text)[:max_chars]
        except Exception as e:
            logger.warning("scrape_failed", url=url, error=str(e))
            return ""

    async def fetch_multiple(self, urls: list[str]) -> list[dict]:
        """Fetch multiple URLs concurrently."""
        import asyncio
        tasks = [self.fetch_text(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            {"url": url, "text": r if isinstance(r, str) else "", "error": str(r) if isinstance(r, Exception) else None}
            for url, r in zip(urls, results)
        ]

    async def fetch_rss(self, url: str, limit: int = 20) -> list[dict]:
        """Parse any RSS/Atom feed."""
        try:
            import feedparser
            async with httpx.AsyncClient(timeout=15, headers=self.HEADERS) as client:
                resp = await client.get(url)
            feed = feedparser.parse(resp.text)
            return [{
                "title": e.get("title", ""),
                "summary": self._clean_html(e.get("summary", ""))[:600],
                "url": e.get("link", ""),
                "published": e.get("published", ""),
            } for e in feed.entries[:limit]]
        except Exception as e:
            logger.warning("rss_failed", url=url, error=str(e))
            return []

    async def fetch_page_metadata(self, url: str) -> dict:
        """Extract OG tags, title, description from a page."""
        html = await self.fetch_text(url, max_chars=20000)
        title = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
        og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
        og_img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
        return {
            "url": url,
            "title": (og_title or title).group(1).strip() if (og_title or title) else "",
            "description": desc.group(1).strip() if desc else "",
            "image": og_img.group(1) if og_img else "",
        }

    def _clean_html(self, html: str) -> str:
        text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


scraper_service = ScraperService()
