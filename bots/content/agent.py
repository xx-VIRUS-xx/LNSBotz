"""
Content Transformation Bot.

Supported transformations:
  - YouTube transcript → LinkedIn post / Twitter thread / short summary
  - PDF / article → quiz / study notes / social post
  - Blog post → Twitter thread
  - Any text → viral hook + rewrite
"""
import httpx
from core.gateway import ai
from core.tools import pdf_extract_url, web_fetch, chunk_text
from core.observability import logger
from .prompts import TRANSFORMATION_PROMPTS


class ContentAgent:
    def __init__(self, user_id: str, config: dict | None = None):
        self.user_id = user_id
        self.config = config or {}

    async def transform(
        self,
        input_type: str,
        source: str,
        output_format: str,
        options: dict | None = None,
    ) -> dict:
        """
        input_type: youtube | pdf_url | article_url | raw_text
        output_format: linkedin_post | twitter_thread | summary | quiz |
                       study_notes | email_newsletter | instagram_caption
        Returns: {"output": str, "word_count": int, "model": str, "cost_usd": float}
        """
        options = options or {}

        # Step 1: Extract source content
        content = await self._extract_content(input_type, source)
        if not content:
            return {"error": "Could not extract content from source"}

        # Step 2: Chunk if too long
        if len(content) > 6000:
            chunks = await chunk_text(content, chunk_size=4000, overlap=200)
            # Summarize each chunk first, then transform the combined summary
            chunk_summaries = []
            for chunk in chunks[:4]:  # process up to 4 chunks
                resp = await ai.complete(
                    messages=[
                        {"role": "system", "content": "Summarize this section concisely in 200 words:"},
                        {"role": "user", "content": chunk},
                    ],
                    task="summarize",
                    user_id=self.user_id,
                    bot_category="content",
                )
                chunk_summaries.append(resp["content"])
            content = "\n\n".join(chunk_summaries)

        # Step 3: Transform
        system_prompt = TRANSFORMATION_PROMPTS.get(output_format, TRANSFORMATION_PROMPTS["summary"])
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Transform this content:\n\n{content}"},
            ],
            task="generate",
            user_id=self.user_id,
            bot_category="content",
        )

        output = resp["content"]
        return {
            "output": output,
            "word_count": len(output.split()),
            "model": resp["model"],
            "cost_usd": resp.get("cost_usd", 0),
            "output_format": output_format,
            "input_type": input_type,
        }

    async def _extract_content(self, input_type: str, source: str) -> str:
        if input_type == "raw_text":
            return source
        elif input_type == "youtube":
            return await self._get_youtube_transcript(source)
        elif input_type == "pdf_url":
            return await pdf_extract_url(source)
        elif input_type == "article_url":
            html = await web_fetch(source)
            return self._strip_html(html)
        return ""

    async def _get_youtube_transcript(self, url: str) -> str:
        """Extract transcript via youtube-transcript-api."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            import re
            video_id = re.search(r"(?:v=|youtu\.be/)([^&\?]+)", url)
            if not video_id:
                return ""
            vid = video_id.group(1)
            transcript = YouTubeTranscriptApi.get_transcript(vid)
            return " ".join([t["text"] for t in transcript])
        except Exception as e:
            logger.warning("youtube_transcript_failed", url=url, error=str(e))
            # Fallback: fetch page description
            page = await web_fetch(url)
            return page[:3000]

    def _strip_html(self, html: str) -> str:
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text[:8000]

    async def batch_transform(self, jobs: list[dict]) -> list[dict]:
        """Process multiple transformation jobs concurrently."""
        import asyncio
        tasks = [
            self.transform(
                j["input_type"], j["source"], j["output_format"], j.get("options")
            )
            for j in jobs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            r if not isinstance(r, Exception) else {"error": str(r)}
            for r in results
        ]
