"""
Shared Translation Service — multilingual, Hindi-first for Indian market.
Uses Gemini for translation (no extra API cost). Supports 20+ languages.
"""
from core.gateway import ai
from core.cache import Cache
import hashlib

_cache = Cache(prefix="trans", ttl=86400)  # 24h cache — translations don't change

SUPPORTED_LANGUAGES = {
    "hi": "Hindi", "bn": "Bengali", "te": "Telugu", "mr": "Marathi",
    "ta": "Tamil", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "or": "Odia", "ur": "Urdu", "en": "English",
    "es": "Spanish", "fr": "French", "de": "German", "ar": "Arabic",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ru": "Russian",
}


class TranslationService:

    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        """Translate text to target language. Cached."""
        cache_key = hashlib.md5(f"{text[:200]}{target_lang}".encode()).hexdigest()
        cached = await _cache.get(cache_key)
        if cached:
            return cached

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        source_hint = f" from {SUPPORTED_LANGUAGES.get(source_lang, 'the detected language')}" if source_lang != "auto" else ""

        resp = await ai.complete(
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate the text{source_hint} to {lang_name}. Output ONLY the translation, nothing else. Preserve formatting, tone, and meaning exactly."},
                {"role": "user", "content": text},
            ],
            task="translate",
            user_id="system",
            bot_category="translation",
        )
        result = resp["content"].strip()
        await _cache.set(cache_key, result)
        return result

    async def translate_to_hindi(self, text: str) -> str:
        return await self.translate(text, "hi")

    async def detect_language(self, text: str) -> str:
        """Detect language of input text."""
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": "Detect the language of the text. Reply with ONLY the ISO 639-1 language code (e.g. 'en', 'hi', 'ta'). Nothing else."},
                {"role": "user", "content": text[:500]},
            ],
            task="classify",
            user_id="system",
            bot_category="translation",
        )
        return resp["content"].strip().lower()[:5]

    async def summarize_in_language(self, text: str, target_lang: str, max_words: int = 150) -> str:
        """Summarize AND translate in one AI call — cheaper than doing both separately."""
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": f"Summarize the following content in {lang_name} in under {max_words} words. Write the summary directly in {lang_name} — do not translate after summarizing. Be clear and informative."},
                {"role": "user", "content": text[:5000]},
            ],
            task="summarize",
            user_id="system",
            bot_category="translation",
        )
        return resp["content"].strip()

    async def generate_subtitles(self, transcript_segments: list[dict], target_lang: str) -> list[dict]:
        """Translate transcript segments for subtitle generation."""
        import asyncio
        batch_text = "\n".join([f"[{i}] {s.get('text','')}" for i, s in enumerate(transcript_segments[:50])])
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": f"Translate these subtitle segments to {SUPPORTED_LANGUAGES.get(target_lang, target_lang)}. Keep the [N] index prefix on each line. Output ONLY the translated segments."},
                {"role": "user", "content": batch_text},
            ],
            task="translate",
            user_id="system",
            bot_category="translation",
        )
        lines = resp["content"].strip().split("\n")
        result = list(transcript_segments)
        for line in lines:
            import re
            m = re.match(r'\[(\d+)\]\s*(.*)', line)
            if m:
                idx, translated = int(m.group(1)), m.group(2)
                if idx < len(result):
                    result[idx] = {**result[idx], "translated_text": translated}
        return result


translation_service = TranslationService()
