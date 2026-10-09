"""
Telegram AI Utility Bot agent.

Handles: text, PDFs, images, voice messages.
Capabilities: research, summarize, translate, Q&A, reminders, file analysis.
"""
import httpx
from core.gateway import ai
from core.memory import SessionMemory
from core.tools import pdf_extract, telegram_send, web_fetch
from core.observability import logger
from .prompts import SYSTEM_PROMPT, INTENT_PROMPT
from .intents import handle_intent


class TelegramAgent:
    def __init__(self, bot_id: str, telegram_token: str):
        self.bot_id = bot_id
        self.token = telegram_token
        self.base_url = f"https://api.telegram.org/bot{telegram_token}"

    async def handle_update(self, update: dict) -> None:
        """Main entry point for all Telegram webhook updates."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = str(message["chat"]["id"])
        user_id = str(message["from"]["id"])
        memory = SessionMemory(self.bot_id, user_id, "telegram")

        try:
            if "text" in message:
                await self._handle_text(message, chat_id, user_id, memory)
            elif "document" in message:
                await self._handle_document(message, chat_id, user_id, memory)
            elif "voice" in message:
                await self._handle_voice(message, chat_id, user_id, memory)
            elif "photo" in message:
                await self._handle_photo(message, chat_id, user_id, memory)
        except Exception as e:
            logger.error("telegram_handle_failed", chat_id=chat_id, error=str(e))
            await telegram_send(chat_id, "Sorry, something went wrong. Please try again.")

    async def _handle_text(self, message: dict, chat_id: str, user_id: str, memory: SessionMemory):
        text = message["text"]

        if text.startswith("/"):
            await self._handle_command(text, chat_id, user_id, memory)
            return

        # Detect intent to route to specialized handlers
        intent = await self._detect_intent(text)

        await memory.add_message("user", text)
        context_msgs = await memory.get_context_messages()

        result = await handle_intent(intent, text, context_msgs, user_id)

        await memory.add_message("assistant", result)
        await telegram_send(chat_id, result)

    async def _handle_command(self, text: str, chat_id: str, user_id: str, memory: SessionMemory):
        cmd = text.split()[0].lower()
        commands = {
            "/start": "👋 Hi! I'm your AI assistant. Send me text, PDFs, voice messages, or images and I'll help you analyze, summarize, research, or transform them.\n\nCommands:\n/help - Show this help\n/clear - Clear conversation history\n/usage - View your usage",
            "/help": "📚 *What I can do:*\n\n• Answer questions & research topics\n• Summarize documents & articles\n• Translate text to any language\n• Analyze PDFs & images\n• Transcribe voice messages\n• Generate content (posts, emails, etc.)\n\nJust send me anything!",
            "/clear": None,  # handled below
        }
        if cmd == "/clear":
            await memory.clear()
            await telegram_send(chat_id, "✅ Conversation history cleared.")
        elif cmd in commands:
            await telegram_send(chat_id, commands[cmd])
        else:
            await telegram_send(chat_id, "Unknown command. Try /help")

    async def _handle_document(self, message: dict, chat_id: str, user_id: str, memory: SessionMemory):
        doc = message["document"]
        caption = message.get("caption", "Summarize this document")
        mime = doc.get("mime_type", "")

        await telegram_send(chat_id, "📄 Processing your document...")

        file_bytes = await self._download_file(doc["file_id"])
        if not file_bytes:
            await telegram_send(chat_id, "❌ Could not download the file.")
            return

        if "pdf" in mime or doc.get("file_name", "").endswith(".pdf"):
            text = await pdf_extract(file_bytes)
        else:
            text = file_bytes.decode("utf-8", errors="ignore")[:8000]

        await memory.add_message("user", f"[Document: {doc.get('file_name', 'file')}]\n{text[:2000]}")
        context_msgs = await memory.get_context_messages()

        resp = await ai.complete(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *context_msgs[:-1],
                {"role": "user", "content": f"User says: '{caption}'\n\nDocument content:\n{text[:6000]}"},
            ],
            task="analyze",
            user_id=user_id,
            bot_category="telegram",
        )
        await memory.add_message("assistant", resp["content"])
        await telegram_send(chat_id, resp["content"])

    async def _handle_voice(self, message: dict, chat_id: str, user_id: str, memory: SessionMemory):
        await telegram_send(chat_id, "🎙️ Transcribing your voice message...")
        file_bytes = await self._download_file(message["voice"]["file_id"])
        if not file_bytes:
            await telegram_send(chat_id, "❌ Could not process voice message.")
            return

        # Transcribe via OpenAI Whisper
        from openai import AsyncOpenAI
        from core.config import settings
        from io import BytesIO
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=("voice.ogg", BytesIO(file_bytes), "audio/ogg"),
        )
        text = transcript.text
        await self._handle_text({"text": text, "from": message["from"]}, chat_id, user_id, memory)

    async def _handle_photo(self, message: dict, chat_id: str, user_id: str, memory: SessionMemory):
        caption = message.get("caption", "What's in this image?")
        await telegram_send(chat_id, "🖼️ Analyzing image...")

        photo = message["photo"][-1]  # largest size
        file_bytes = await self._download_file(photo["file_id"])
        if not file_bytes:
            await telegram_send(chat_id, "❌ Could not process image.")
            return

        import base64
        from openai import AsyncOpenAI
        from core.config import settings
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        b64 = base64.b64encode(file_bytes).decode()
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            max_tokens=1024,
        )
        result = resp.choices[0].message.content
        await memory.add_message("user", f"[Image] {caption}")
        await memory.add_message("assistant", result)
        await telegram_send(chat_id, result)

    async def _detect_intent(self, text: str) -> str:
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": text},
            ],
            task="classify",
            use_cache=True,
            user_id="system",
            bot_category="telegram",
        )
        intent = resp["content"].strip().lower().split()[0]
        valid = {"research", "summarize", "translate", "generate", "calculate", "chat", "analyze"}
        return intent if intent in valid else "chat"

    async def _download_file(self, file_id: str) -> bytes | None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.base_url}/getFile?file_id={file_id}")
            data = resp.json()
            if not data.get("ok"):
                return None
            file_path = data["result"]["file_path"]
            file_resp = await client.get(
                f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            )
            return file_resp.content
