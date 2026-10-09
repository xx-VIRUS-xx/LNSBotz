"""
Local Business AI Agent.

Handles: WhatsApp/Telegram inquiries → qualify leads → book appointments
         → CRM memory → follow-up automation → campaign generation.
"""
from datetime import datetime, timezone
from core.gateway import ai
from core.memory import SessionMemory
from core.tools import telegram_send, email_send
from core.observability import logger
from .prompts import build_system_prompt, LEAD_QUALIFY_PROMPT, FOLLOW_UP_PROMPT


class BusinessAgent:
    def __init__(self, bot_id: str, user_id: str, config: dict):
        self.bot_id = bot_id
        self.user_id = user_id
        self.business_name: str = config.get("business_name", "Our Business")
        self.business_type: str = config.get("business_type", "service")
        self.services: list[str] = config.get("services", [])
        self.owner_contact: dict = config.get("owner_contact", {})
        self.auto_qualify: bool = config.get("auto_qualify", True)
        self.booking_url: str = config.get("booking_url", "")
        self.platform: str = config.get("platform", "telegram")

    async def handle_message(self, external_user_id: str, message: str, channel: str = "telegram") -> str:
        """Handle an incoming customer message."""
        memory = SessionMemory(self.bot_id, external_user_id, channel)

        # First message — qualify the lead
        msgs = await memory.get_messages()
        is_first_message = len(msgs) == 0

        await memory.add_message("user", message)
        context = await memory.get_context_messages()

        system_prompt = build_system_prompt(
            business_name=self.business_name,
            business_type=self.business_type,
            services=self.services,
            booking_url=self.booking_url,
        )

        resp = await ai.complete(
            messages=[{"role": "system", "content": system_prompt}, *context],
            task="chat",
            temperature=0.5,
            user_id=self.user_id,
            bot_category="business",
        )
        reply = resp["content"]
        await memory.add_message("assistant", reply)

        # Background: qualify lead on first message
        if is_first_message and self.auto_qualify:
            lead_data = await self._qualify_lead(message, external_user_id)
            await memory.set_metadata("lead_score", lead_data.get("score", 0))
            await memory.set_metadata("lead_intent", lead_data.get("intent", "unknown"))

            # Notify owner if high-value lead
            if lead_data.get("score", 0) >= 7:
                await self._notify_owner(external_user_id, message, lead_data)

        return reply

    async def _qualify_lead(self, message: str, user_id: str) -> dict:
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": LEAD_QUALIFY_PROMPT.format(
                    business_name=self.business_name,
                    business_type=self.business_type,
                    services=", ".join(self.services),
                )},
                {"role": "user", "content": message},
            ],
            task="classify",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="business",
        )
        import json
        try:
            return json.loads(resp["content"])
        except Exception:
            return {"score": 5, "intent": "inquiry", "summary": message[:100]}

    async def _notify_owner(self, customer_id: str, message: str, lead_data: dict) -> None:
        owner_email = self.owner_contact.get("email")
        owner_telegram = self.owner_contact.get("telegram_chat_id")
        notification = (
            f"🔥 *High-value lead detected!*\n\n"
            f"Business: {self.business_name}\n"
            f"Customer ID: {customer_id}\n"
            f"Lead score: {lead_data.get('score', 'N/A')}/10\n"
            f"Intent: {lead_data.get('intent', 'N/A')}\n"
            f"Message: {message[:200]}"
        )
        if owner_telegram:
            await telegram_send(owner_telegram, notification)
        if owner_email:
            await email_send(
                to=owner_email,
                subject=f"[{self.business_name}] New High-Value Lead",
                body=notification.replace("*", "").replace("_", ""),
            )

    async def generate_campaign(self, campaign_type: str, target_audience: str, goal: str) -> dict:
        """Generate a marketing campaign (messages, posts, ad copy)."""
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": f"""You are a marketing strategist for {self.business_name}.
Create a complete {campaign_type} campaign.
Target: {target_audience}
Goal: {goal}
Services: {', '.join(self.services)}

Generate:
1. WhatsApp/SMS message (under 160 chars)
2. Instagram caption with hashtags
3. Google Ad headline + description
4. Email subject + 150-word body
Return as JSON with keys: whatsapp, instagram, google_ad, email"""},
                {"role": "user", "content": f"Create a {campaign_type} campaign targeting {target_audience} to {goal}"},
            ],
            task="generate",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="business",
        )
        import json
        try:
            return json.loads(resp["content"])
        except Exception:
            return {"raw": resp["content"]}

    async def generate_follow_up(self, customer_history: list[dict], days_since_last: int) -> str:
        """Generate a personalized follow-up message."""
        history_text = "\n".join([f"- {m['role']}: {m['content'][:100]}" for m in customer_history[-5:]])
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": FOLLOW_UP_PROMPT.format(
                    business_name=self.business_name,
                    days=days_since_last,
                )},
                {"role": "user", "content": f"Customer history:\n{history_text}"},
            ],
            task="generate",
            user_id=self.user_id,
            bot_category="business",
        )
        return resp["content"]
