"""
Document Agent — shared by invoice, legal, GST, resume, RTI products.
One agent, many configured product types.
"""
import json
from core.gateway import ai
from core.services import document_service, translation_service
from core.observability import logger

PRODUCT_PROMPTS = {
    "invoice": """You are an invoice analysis expert. Extract and analyze this invoice.
Return JSON:
{
  "vendor": "vendor name",
  "invoice_number": "...",
  "date": "...",
  "due_date": "...",
  "items": [{"description": "...", "quantity": 0, "unit_price": 0, "total": 0}],
  "subtotal": 0,
  "tax": 0,
  "total_amount": 0,
  "currency": "INR",
  "payment_terms": "...",
  "red_flags": ["any suspicious items or discrepancies"],
  "summary": "one sentence summary"
}""",

    "legal_notice": """You are a legal expert. Analyze this legal notice for a common person.
Return JSON:
{
  "notice_type": "type of legal notice",
  "sender": "who sent it",
  "recipient": "who received it",
  "key_demands": ["what is being demanded"],
  "deadline": "response deadline if any",
  "consequences": "what happens if ignored",
  "simple_explanation": "explain in simple language what this means",
  "urgency": "critical|high|medium|low",
  "recommended_action": "what the recipient should do",
  "legal_sections": ["sections cited"]
}""",

    "gst": """You are a GST expert for India. Analyze this GST-related document.
Return JSON:
{
  "document_type": "GSTR-1|GSTR-3B|GST invoice|GST notice|other",
  "gstin": "GSTIN number if present",
  "period": "tax period",
  "total_taxable_value": 0,
  "cgst": 0,
  "sgst": 0,
  "igst": 0,
  "total_tax": 0,
  "simple_explanation": "explain in plain Hindi/English what this document means",
  "action_required": "what action is needed",
  "deadline": "any deadline mentioned",
  "red_flags": ["compliance issues or discrepancies"]
}""",

    "resume": """You are an expert recruiter and career coach. Review this resume.
Return JSON:
{
  "candidate_name": "...",
  "current_role": "...",
  "years_experience": 0,
  "skills": ["skill1", "skill2"],
  "education": "highest qualification",
  "strengths": ["top 3 strengths"],
  "weaknesses": ["top 3 areas to improve"],
  "ats_score": 0,
  "overall_rating": "1-10",
  "summary": "2 sentence professional summary",
  "suggestions": ["actionable improvement suggestions"],
  "suitable_roles": ["roles this person is suitable for"]
}""",

    "rti": """You are an RTI (Right to Information) expert for India.
Analyze this RTI-related document and return JSON:
{
  "document_type": "RTI application|RTI reply|first appeal|second appeal|rejection",
  "subject": "what information is being sought",
  "public_authority": "which government body",
  "status": "pending|replied|rejected|appealed",
  "information_provided": "summary of what was provided",
  "rejection_reason": "reason if rejected",
  "simple_explanation": "what this document means in plain language",
  "next_steps": "what the applicant should do next",
  "time_limit": "applicable time limit",
  "relevant_sections": ["RTI Act sections cited"]
}""",

    "property": """You are a property document expert in India. Analyze this document.
Return JSON:
{
  "document_type": "sale deed|lease|agreement|title deed|encumbrance certificate|other",
  "property_description": "brief property description",
  "parties": ["buyer/seller/lessor/lessee names"],
  "property_value": 0,
  "key_terms": ["important terms and conditions"],
  "red_flags": ["potential legal or financial risks"],
  "stamp_duty_status": "paid/unpaid/unknown",
  "registration_status": "registered/unregistered/unknown",
  "simple_explanation": "plain language summary",
  "recommended_actions": ["what to verify or do"]
}""",
}


class DocumentAgent:
    def __init__(self, product_type: str, user_id: str, output_language: str = "en"):
        self.product_type = product_type
        self.user_id = user_id
        self.output_language = output_language

    async def analyze(self, source: bytes | str, filename: str = "") -> dict:
        """
        source: PDF bytes, image bytes, or raw text string
        Returns structured analysis dict + plain language explanation
        """
        # Step 1: Extract text
        text = await self._extract_text(source, filename)
        if not text or len(text.strip()) < 50:
            return {"error": "Could not extract readable text from document"}

        # Step 2: Auto-detect type if not specified
        product = self.product_type
        if product == "auto":
            product = await document_service.detect_document_type(text)

        # Step 3: Analyze
        prompt = PRODUCT_PROMPTS.get(product, PRODUCT_PROMPTS["legal_notice"])
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Document content:\n\n{text[:6000]}"},
            ],
            task="analyze",
            response_format={"type": "json_object"},
            user_id=self.user_id,
            bot_category="document",
        )

        try:
            result = json.loads(resp["content"])
        except Exception:
            result = {"summary": resp["content"], "raw": True}

        result["product_type"] = product
        result["char_count"] = len(text)

        # Step 4: Translate explanation if non-English output requested
        if self.output_language != "en":
            explanation_key = next((k for k in ["simple_explanation", "summary", "plain_summary"] if k in result), None)
            if explanation_key:
                result[explanation_key] = await translation_service.translate(
                    result[explanation_key], self.output_language
                )

        return result

    async def _extract_text(self, source: bytes | str, filename: str) -> str:
        if isinstance(source, str):
            if source.startswith("http"):
                return await document_service.extract_pdf(source)
            return source  # raw text passed directly

        fname = filename.lower()
        if fname.endswith(".pdf") or (isinstance(source, bytes) and source[:4] == b"%PDF"):
            return await document_service.extract_pdf(source)
        elif any(fname.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return await document_service.extract_image_text(source)
        else:
            # Try as text
            try:
                return source.decode("utf-8", errors="ignore")
            except Exception:
                return ""

    def format_for_telegram(self, result: dict) -> str:
        """Format analysis result for Telegram delivery."""
        ptype = result.get("product_type", "document").replace("_", " ").title()
        lines = [f"📄 *{ptype} Analysis*\n"]

        # Show most important fields based on type
        important = {
            "invoice": ["vendor", "total_amount", "due_date", "summary", "red_flags"],
            "legal_notice": ["notice_type", "simple_explanation", "deadline", "urgency", "recommended_action"],
            "gst": ["document_type", "total_tax", "simple_explanation", "action_required", "deadline"],
            "resume": ["current_role", "overall_rating", "strengths", "suggestions"],
            "rti": ["subject", "status", "simple_explanation", "next_steps"],
            "property": ["document_type", "property_value", "red_flags", "recommended_actions"],
        }.get(result.get("product_type", ""), ["summary", "simple_explanation"])

        for key in important:
            val = result.get(key)
            if not val:
                continue
            label = key.replace("_", " ").title()
            if isinstance(val, list):
                lines.append(f"*{label}:*")
                for item in val[:4]:
                    lines.append(f"  • {item}")
            else:
                lines.append(f"*{label}:* {str(val)[:200]}")

        return "\n".join(lines)[:4000]
