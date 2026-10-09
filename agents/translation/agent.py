"""
Translation Agent — multilingual conversion, Hindi content, subtitles, TTS.
Shared by all multilingual products.
"""
import json
from core.gateway import ai
from core.services import translation_service, document_service, scraper_service
from core.observability import logger

TTS_SCRIPT_PROMPT = """You are a professional voice-over scriptwriter for Indian audiences.
Convert the content into a natural voice-over script.
Requirements:
- Conversational, natural-sounding language
- Short sentences (max 15 words each)
- Appropriate pauses marked with [PAUSE]
- Emphasis marked with *word*
- Target duration: {duration} seconds at 130 words/minute
- Language: {language}
Output ONLY the script, ready for TTS."""


class TranslationAgent:
    def __init__(self, user_id: str, config: dict | None = None):
        self.user_id = user_id
        self.config = config or {}

    async def translate_document(self, source: bytes | str, target_lang: str, filename: str = "") -> dict:
        """Extract + translate a full document."""
        if isinstance(source, bytes):
            text = await document_service.extract_pdf(source)
        elif source.startswith("http"):
            text = await scraper_service.fetch_text(source)
        else:
            text = source

        if len(text) > 6000:
            chunks = await document_service.chunk_document(text, 3000, 300)
            translated_chunks = []
            for chunk in chunks[:6]:
                translated = await translation_service.translate(chunk, target_lang)
                translated_chunks.append(translated)
            translated_text = "\n\n".join(translated_chunks)
        else:
            translated_text = await translation_service.translate(text, target_lang)

        return {
            "original_length": len(text),
            "translated_text": translated_text,
            "target_language": target_lang,
            "source_language": await translation_service.detect_language(text[:200]),
        }

    async def news_to_hindi(self, url_or_text: str) -> dict:
        """Convert English news to Hindi summary — for Hindi news products."""
        if url_or_text.startswith("http"):
            text = await scraper_service.fetch_text(url_or_text)
        else:
            text = url_or_text

        hindi_summary = await translation_service.summarize_in_language(text, "hi", max_words=150)
        hindi_headline = await translation_service.translate(
            text[:200].split(".")[0], "hi"
        )
        tts_script = await self._generate_tts_script(hindi_summary, "Hindi", duration=60)

        return {
            "original_text": text[:500],
            "hindi_headline": hindi_headline,
            "hindi_summary": hindi_summary,
            "tts_script": tts_script,
            "word_count": len(hindi_summary.split()),
        }

    async def generate_subtitles(self, transcript: list[dict] | str, target_lang: str) -> list[dict]:
        """Generate translated subtitles from transcript segments or text."""
        if isinstance(transcript, str):
            words = transcript.split()
            segment_size = 10
            segments = []
            for i in range(0, len(words), segment_size):
                segments.append({
                    "text": " ".join(words[i:i+segment_size]),
                    "start": i * 0.5,
                    "end": (i + segment_size) * 0.5,
                })
        else:
            segments = transcript

        translated = await translation_service.generate_subtitles(segments, target_lang)
        return translated

    async def regional_summarize(self, text: str, language: str) -> str:
        """Summarize content in a regional Indian language."""
        return await translation_service.summarize_in_language(text, language)

    async def _generate_tts_script(self, text: str, language: str, duration: int = 60) -> str:
        """Generate natural TTS-ready script."""
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": TTS_SCRIPT_PROMPT.format(duration=duration, language=language)},
                {"role": "user", "content": text},
            ],
            task="generate",
            user_id=self.user_id,
            bot_category="translation",
        )
        return resp["content"]

    async def create_multilingual_content(self, text: str, languages: list[str]) -> dict:
        """Create content in multiple languages simultaneously."""
        import asyncio
        tasks = {lang: translation_service.translate(text, lang) for lang in languages}
        results = {}
        for lang, coro in tasks.items():
            try:
                results[lang] = await coro
            except Exception as e:
                results[lang] = f"Error: {e}"
        return results
