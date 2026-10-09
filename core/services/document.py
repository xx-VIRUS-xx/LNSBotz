"""
Shared Document Service — PDF, OCR, invoices, legal docs.
All document-type agents use this. Never duplicate parsing logic.
"""
import asyncio
from io import BytesIO
from core.observability import logger


class DocumentService:

    async def extract_pdf(self, source: bytes | str) -> str:
        """Extract text from PDF bytes or URL."""
        if isinstance(source, str):
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(source)
                resp.raise_for_status()
            source = resp.content

        def _extract(data: bytes) -> str:
            import pdfplumber
            parts = []
            with pdfplumber.open(BytesIO(data)) as pdf:
                for page in pdf.pages[:40]:
                    text = page.extract_text()
                    if text:
                        parts.append(text)
            return "\n\n".join(parts)

        return await asyncio.get_event_loop().run_in_executor(None, _extract, source)

    async def extract_tables_from_pdf(self, pdf_bytes: bytes) -> list[list]:
        """Extract tables from PDF (useful for invoices, GST forms)."""
        def _extract(data: bytes) -> list:
            import pdfplumber
            all_tables = []
            with pdfplumber.open(BytesIO(data)) as pdf:
                for page in pdf.pages[:10]:
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
            return all_tables

        return await asyncio.get_event_loop().run_in_executor(None, _extract, pdf_bytes)

    async def extract_image_text(self, image_bytes: bytes) -> str:
        """OCR from image using Gemini vision (no Tesseract needed)."""
        import base64
        import google.generativeai as genai
        from core.config import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)

        model = genai.GenerativeModel("gemini-2.0-flash")
        b64 = base64.b64encode(image_bytes).decode()
        resp = await model.generate_content_async([
            "Extract ALL text from this image exactly as it appears. Include numbers, dates, amounts. Output only the extracted text.",
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
        ])
        return resp.text

    async def chunk_document(self, text: str, chunk_size: int = 3000, overlap: int = 300) -> list[str]:
        """Split large documents for processing."""
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + chunk_size])
            start += chunk_size - overlap
        return chunks

    async def detect_document_type(self, text: str) -> str:
        """Classify document type from content."""
        from core.gateway import ai
        resp = await ai.complete(
            messages=[
                {"role": "system", "content": "Classify this document. Reply with ONE word from: invoice, legal_notice, contract, resume, gst_form, rti, tender, news_article, government_order, property_document, other"},
                {"role": "user", "content": text[:1000]},
            ],
            task="classify",
            user_id="system",
            bot_category="document",
        )
        return resp["content"].strip().lower().split()[0]


document_service = DocumentService()
