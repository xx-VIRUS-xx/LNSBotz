"""
Shared Search Service — web, news, social, government.
All agents use this. Never duplicate search logic in individual agents.
"""
import httpx
import urllib.parse
from core.observability import logger


class SearchService:

    async def web(self, query: str, max_results: int = 10) -> list[dict]:
        """DuckDuckGo instant search — no API key needed."""
        q = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers={"User-Agent": "LateNightStack/1.0"})
            data = resp.json()
            results = []
            abstract = data.get("AbstractText", "")
            if abstract:
                results.append({"title": data.get("Heading", query), "snippet": abstract,
                                 "url": data.get("AbstractURL", ""), "source": "duckduckgo"})
            for r in data.get("RelatedTopics", [])[:max_results - 1]:
                if isinstance(r, dict) and "Text" in r:
                    results.append({"title": r.get("Text", "")[:80], "snippet": r.get("Text", ""),
                                    "url": r.get("FirstURL", ""), "source": "duckduckgo"})
            return results
        except Exception as e:
            logger.warning("search_web_failed", query=query, error=str(e))
            return []

    async def news(self, query: str, max_results: int = 10) -> list[dict]:
        """Google News RSS — no API key needed."""
        q = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            import feedparser
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers={"User-Agent": "LateNightStack/1.0"})
            feed = feedparser.parse(resp.text)
            results = []
            for entry in feed.entries[:max_results]:
                results.append({
                    "title": entry.get("title", ""),
                    "snippet": entry.get("summary", "")[:500],
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": "google_news",
                })
            return results
        except Exception as e:
            logger.warning("search_news_failed", query=query, error=str(e))
            return []

    async def hindi_news(self, query: str, max_results: int = 10) -> list[dict]:
        """Google News RSS in Hindi."""
        q = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=hi&gl=IN&ceid=IN:hi"
        try:
            import feedparser
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers={"User-Agent": "LateNightStack/1.0"})
            feed = feedparser.parse(resp.text)
            return [{"title": e.get("title", ""), "snippet": e.get("summary", "")[:500],
                     "url": e.get("link", ""), "published": e.get("published", ""),
                     "source": "google_news_hindi"} for e in feed.entries[:max_results]]
        except Exception as e:
            logger.warning("search_hindi_news_failed", error=str(e))
            return []

    async def reddit(self, subreddit: str, query: str = "", limit: int = 25) -> list[dict]:
        """Reddit search via public JSON API."""
        if query:
            url = f"https://www.reddit.com/r/{subreddit}/search.json?q={urllib.parse.quote(query)}&restrict_sr=1&limit={limit}"
        else:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.get(url, headers={"User-Agent": "LateNightStack/1.0"})
                resp.raise_for_status()
            data = resp.json()
            posts = []
            for item in data["data"]["children"]:
                p = item["data"]
                posts.append({
                    "id": p["id"], "title": p["title"], "score": p["score"],
                    "text": p.get("selftext", "")[:1000], "url": p.get("url", ""),
                    "permalink": f"https://reddit.com{p.get('permalink','')}",
                    "num_comments": p.get("num_comments", 0),
                    "created_utc": p.get("created_utc", 0), "source": "reddit",
                })
            return posts
        except Exception as e:
            logger.warning("search_reddit_failed", subreddit=subreddit, error=str(e))
            return []

    async def twitter_trends(self, woeid: int = 23424848) -> list[dict]:
        """Public Twitter/X trends — India WOEID=23424848."""
        # Nitter RSS as public fallback
        try:
            import feedparser
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://trends24.in/india/", headers={"User-Agent": "LateNightStack/1.0"})
            # Parse trending topics from trends24
            import re
            trends = re.findall(r'<a[^>]+trend-name[^>]*>([^<]+)</a>', resp.text)
            return [{"trend": t.strip(), "source": "trends24"} for t in trends[:20]]
        except Exception as e:
            logger.warning("twitter_trends_failed", error=str(e))
            return []

    async def jobs(self, query: str, location: str = "India") -> list[dict]:
        """Job listings via Google News job search."""
        return await self.news(f"{query} jobs hiring {location}")

    async def government_tenders(self, keyword: str) -> list[dict]:
        """Government tender search via news + GeM portal RSS."""
        results = await self.news(f"government tender {keyword} site:gem.gov.in OR site:eprocure.gov.in")
        gem_results = await self.news(f"GeM tender {keyword}")
        return results + gem_results


search_service = SearchService()
