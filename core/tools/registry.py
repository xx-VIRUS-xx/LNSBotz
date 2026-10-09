"""
Reusable tool registry — every bot imports tools from here.
Tools are plain async functions decorated with @tool.
"""
import asyncio
import httpx
import feedparser
import pdfplumber
from io import BytesIO
from typing import Any
from core.observability import logger


_TOOLS: dict[str, callable] = {}


def tool(name: str | None = None):
    """Decorator to register a function as a named tool."""
    def decorator(fn):
        key = name or fn.__name__
        _TOOLS[key] = fn
        return fn
    return decorator


def get_tool(name: str) -> callable:
    if name not in _TOOLS:
        raise KeyError(f"Tool '{name}' not found. Available: {list(_TOOLS.keys())}")
    return _TOOLS[name]


def list_tools() -> list[str]:
    return list(_TOOLS.keys())


# ── Web / Search Tools ────────────────────────────────────────────────────────

@tool("web_fetch")
async def web_fetch(url: str, timeout: int = 15) -> str:
    """Fetch raw text content from a URL."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BotEcosystem/1.0)"})
        resp.raise_for_status()
        return resp.text[:50000]  # cap at 50KB


@tool("rss_fetch")
async def rss_fetch(feed_url: str) -> list[dict]:
    """Parse an RSS/Atom feed and return recent entries."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(feed_url)
    feed = feedparser.parse(resp.text)
    entries = []
    for entry in feed.entries[:20]:
        entries.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "")[:500],
            "published": entry.get("published", ""),
        })
    return entries


@tool("reddit_fetch")
async def reddit_fetch(subreddit: str, limit: int = 25, sort: str = "hot") -> list[dict]:
    """Fetch posts from a subreddit via public JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"User-Agent": "BotEcosystem/1.0"})
        resp.raise_for_status()
    data = resp.json()
    posts = []
    for post in data["data"]["children"]:
        p = post["data"]
        posts.append({
            "id": p["id"],
            "title": p["title"],
            "score": p["score"],
            "url": p.get("url", ""),
            "selftext": p.get("selftext", "")[:1000],
            "num_comments": p.get("num_comments", 0),
            "created_utc": p.get("created_utc", 0),
            "permalink": f"https://reddit.com{p.get('permalink', '')}",
        })
    return posts


# ── Document Tools ────────────────────────────────────────────────────────────

@tool("pdf_extract")
async def pdf_extract(pdf_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    def _extract(data: bytes) -> str:
        text_parts = []
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages[:30]:  # limit to 30 pages
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract, pdf_bytes)


@tool("pdf_extract_url")
async def pdf_extract_url(url: str) -> str:
    """Download and extract text from a PDF at a URL."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return await pdf_extract(resp.content)


# ── Messaging Tools ───────────────────────────────────────────────────────────

@tool("telegram_send")
async def telegram_send(chat_id: str, text: str, parse_mode: str = "Markdown") -> dict:
    """Send a message via Telegram Bot API."""
    from core.config import settings
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4096], "parse_mode": parse_mode}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
    return resp.json()


@tool("email_send")
async def email_send(to: str, subject: str, body: str, html: bool = False) -> bool:
    """Send an email via SMTP."""
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from core.config import settings

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = to
    mime_type = "html" if html else "plain"
    msg.attach(MIMEText(body, mime_type))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        start_tls=True,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
    )
    return True


# ── Text Processing Tools ─────────────────────────────────────────────────────

@tool("chunk_text")
async def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for embedding or processing."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


@tool("extract_keywords")
async def extract_keywords(text: str) -> list[str]:
    """Naïve keyword extraction by frequency (no AI cost)."""
    import re
    from collections import Counter
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    stopwords = {"that", "this", "with", "from", "have", "will", "been", "they", "their",
                 "what", "when", "where", "which", "more", "about", "into", "also", "just"}
    words = [w for w in words if w not in stopwords]
    return [w for w, _ in Counter(words).most_common(15)]
