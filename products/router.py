"""
Unified Products Router — all 30+ products in one file.
Each product is a configured instance of a shared agent.
This is the key architectural insight: products = config, not code.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Literal, Optional
from core.db import User
from core.auth import get_current_user_flexible

router = APIRouter(prefix="/products", tags=["Products"])

# ── Request Models ────────────────────────────────────────────────────────────

class IntelligenceRequest(BaseModel):
    product: Literal[
        "competitor_tracker", "political_narrative", "reddit_sentiment",
        "tender_alert", "stock_news", "job_monitor", "x_trends",
        "news_summarizer", "constituency_sentiment", "election_monitor"
    ]
    keywords: list[str]
    sources: list[dict] | None = None
    delivery: dict | None = None
    language: str = "en"

class DocumentRequest(BaseModel):
    product: Literal["invoice", "legal_notice", "gst", "resume", "rti", "property", "auto"]
    text: str | None = None
    url: str | None = None
    output_language: str = "en"

class ContentRequest(BaseModel):
    product: Literal[
        "video_to_reels", "tweet_to_carousel", "blog_to_linkedin",
        "pdf_to_quiz", "notes_to_flashcards", "podcast_to_clips", "blog_to_thread"
    ]
    source: str
    input_type: Literal["youtube", "pdf_url", "article_url", "raw_text"] = "raw_text"
    output_language: str = "en"

class PoliticalRequest(BaseModel):
    product: Literal[
        "speech_summarizer", "narrative", "constituency",
        "election_monitor", "trend_analyzer"
    ]
    keywords: list[str] = []
    politicians: list[str] = []
    constituency: str = ""
    delivery: dict | None = None
    language: str = "en"

class TranslationRequest(BaseModel):
    product: Literal[
        "translate", "hindi_news", "regional_summary",
        "subtitle_generator", "multilingual"
    ]
    text: str | None = None
    url: str | None = None
    target_language: str = "hi"
    languages: list[str] | None = None

class PropertyRequest(BaseModel):
    product: Literal["listing_analyzer", "market_intelligence", "fraud_check"]
    text: str | None = None
    url: str | None = None
    location: str = ""


# ── Intelligence Products ─────────────────────────────────────────────────────

INTELLIGENCE_SOURCE_DEFAULTS = {
    "competitor_tracker":      [{"type": "news"}, {"type": "reddit", "subreddit": "india"}],
    "political_narrative":     [{"type": "news"}, {"type": "hindi_news"}, {"type": "reddit", "subreddit": "IndiaSpeaks"}],
    "reddit_sentiment":        [{"type": "reddit", "subreddit": "india"}],
    "tender_alert":            [{"type": "tender"}],
    "stock_news":              [{"type": "news"}],
    "job_monitor":             [{"type": "jobs"}],
    "x_trends":                [{"type": "twitter_trends"}],
    "news_summarizer":         [{"type": "news"}, {"type": "hindi_news"}],
    "constituency_sentiment":  [{"type": "news"}, {"type": "hindi_news"}, {"type": "reddit", "subreddit": "india"}],
    "election_monitor":        [{"type": "news"}, {"type": "hindi_news"}, {"type": "reddit", "subreddit": "IndiaSpeaks"}],
}

@router.post("/intelligence", summary="Run any intelligence monitoring product")
async def run_intelligence(
    req: IntelligenceRequest,
    user: User = Depends(get_current_user_flexible),
):
    from agents.intelligence.agent import IntelligenceAgent
    sources = req.sources or INTELLIGENCE_SOURCE_DEFAULTS.get(req.product, [{"type": "news"}])
    agent = IntelligenceAgent(
        product_type=req.product,
        user_id=str(user.id),
        config={"keywords": req.keywords, "sources": sources,
                "delivery": req.delivery or {}, "language": req.language},
    )
    return await agent.run()


# ── Document Intelligence Products ───────────────────────────────────────────

@router.post("/document/analyze", summary="Analyze any document (invoice, legal, GST, resume, RTI)")
async def analyze_document(
    req: DocumentRequest,
    user: User = Depends(get_current_user_flexible),
):
    from agents.document.agent import DocumentAgent
    agent = DocumentAgent(req.product, str(user.id), req.output_language)
    source = req.url or req.text
    if not source:
        raise HTTPException(400, "Provide either 'text' or 'url'")
    result = await agent.analyze(source)
    return result


@router.post("/document/upload", summary="Upload and analyze a document file")
async def analyze_document_upload(
    product: str = Form("auto"),
    output_language: str = Form("en"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user_flexible),
):
    from agents.document.agent import DocumentAgent
    content = await file.read()
    agent = DocumentAgent(product, str(user.id), output_language)
    result = await agent.analyze(content, filename=file.filename or "")
    return result


# ── Content Transformation Products ──────────────────────────────────────────

CONTENT_FORMAT_MAP = {
    "video_to_reels":        ("youtube",      "twitter_thread"),
    "tweet_to_carousel":     ("raw_text",     "instagram_caption"),
    "blog_to_linkedin":      ("article_url",  "linkedin_post"),
    "pdf_to_quiz":           ("pdf_url",      "quiz"),
    "notes_to_flashcards":   ("raw_text",     "study_notes"),
    "podcast_to_clips":      ("youtube",      "summary"),
    "blog_to_thread":        ("article_url",  "twitter_thread"),
}

@router.post("/content/transform", summary="Transform content (video, blog, PDF, tweets)")
async def transform_content(
    req: ContentRequest,
    user: User = Depends(get_current_user_flexible),
):
    from bots.content.agent import ContentAgent
    from core.services import translation_service

    default_input, default_output = CONTENT_FORMAT_MAP.get(req.product, ("raw_text", "summary"))
    agent = ContentAgent(user_id=str(user.id))
    result = await agent.transform(
        input_type=req.input_type or default_input,
        source=req.source,
        output_format=default_output,
    )
    # Translate output if non-English requested
    if req.output_language != "en" and result.get("output"):
        result["output"] = await translation_service.translate(result["output"], req.output_language)
        result["output_language"] = req.output_language
    return result


# ── Political Intelligence Products ──────────────────────────────────────────

@router.post("/political", summary="Political intelligence (narratives, speeches, constituency)")
async def run_political(
    req: PoliticalRequest,
    user: User = Depends(get_current_user_flexible),
):
    from agents.political.agent import PoliticalAgent
    agent = PoliticalAgent(
        product_type=req.product,
        user_id=str(user.id),
        config={"keywords": req.keywords, "politicians": req.politicians,
                "constituency": req.constituency, "delivery": req.delivery or {},
                "language": req.language},
    )
    return await agent.run()


# ── Multilingual Products ─────────────────────────────────────────────────────

@router.post("/multilingual", summary="Translation, Hindi news, regional content, subtitles")
async def run_multilingual(
    req: TranslationRequest,
    user: User = Depends(get_current_user_flexible),
):
    from agents.translation.agent import TranslationAgent
    agent = TranslationAgent(user_id=str(user.id))

    if req.product == "translate":
        source = req.text or (await __import__('core.services', fromlist=['scraper_service']).scraper_service.fetch_text(req.url) if req.url else "")
        return {"translated": await __import__('core.services', fromlist=['translation_service']).translation_service.translate(source, req.target_language)}

    elif req.product == "hindi_news":
        source = req.url or req.text or ""
        return await agent.news_to_hindi(source)

    elif req.product == "regional_summary":
        from core.services import scraper_service
        text = req.text or (await scraper_service.fetch_text(req.url) if req.url else "")
        summary = await agent.regional_summarize(text, req.target_language)
        return {"summary": summary, "language": req.target_language}

    elif req.product == "subtitle_generator":
        text = req.text or ""
        subtitles = await agent.generate_subtitles(text, req.target_language)
        return {"subtitles": subtitles, "language": req.target_language}

    elif req.product == "multilingual":
        text = req.text or ""
        langs = req.languages or ["hi", "bn", "te", "mr", "ta"]
        return await agent.create_multilingual_content(text, langs)

    raise HTTPException(400, f"Unknown product: {req.product}")


# ── Real Estate Products ──────────────────────────────────────────────────────

@router.post("/property", summary="Property listing analysis, market intelligence, fraud detection")
async def run_property(
    req: PropertyRequest,
    user: User = Depends(get_current_user_flexible),
):
    from agents.property.agent import PropertyAgent
    agent = PropertyAgent(user_id=str(user.id))

    if req.product == "listing_analyzer":
        return await agent.analyze_listing(listing_text=req.text, listing_url=req.url)
    elif req.product == "market_intelligence":
        return await agent.get_market_intelligence(req.location, "")
    elif req.product == "fraud_check":
        text = req.text or ""
        flags = await agent.detect_fraud_indicators(text)
        return {"fraud_flags": flags, "risk_level": "high" if len(flags) > 2 else "medium" if flags else "low"}

    raise HTTPException(400, f"Unknown product: {req.product}")


# ── Product Catalog ───────────────────────────────────────────────────────────

@router.get("/catalog", summary="List all available products")
async def get_catalog():
    return {
        "intelligence": [
            {"id": "competitor_tracker", "name": "Competitor Post Tracker", "description": "Monitor competitor activity across news and social"},
            {"id": "political_narrative", "name": "Political Narrative Tracker", "description": "Track political narratives in news and social media"},
            {"id": "reddit_sentiment", "name": "Reddit Sentiment Bot", "description": "Monitor Reddit for brand/topic sentiment"},
            {"id": "tender_alert", "name": "Government Tender Alert", "description": "Get alerted on new government tenders"},
            {"id": "stock_news", "name": "Stock / News Watcher", "description": "Monitor news for specific stocks or companies"},
            {"id": "job_monitor", "name": "Job Opening Monitor", "description": "Track hiring trends for specific roles/companies"},
            {"id": "x_trends", "name": "X Trend Detector", "description": "Monitor Twitter/X trending topics"},
            {"id": "news_summarizer", "name": "RTI / News Summarizer", "description": "Summarize news and RTI responses"},
            {"id": "constituency_sentiment", "name": "Constituency Sentiment Tracker", "description": "Track public sentiment in a constituency"},
            {"id": "election_monitor", "name": "Election Narrative Monitor", "description": "Monitor election coverage and narratives"},
        ],
        "document": [
            {"id": "invoice", "name": "Invoice Summarizer", "description": "Extract and analyze invoices"},
            {"id": "legal_notice", "name": "Legal Notice Simplifier", "description": "Explain legal notices in plain language"},
            {"id": "gst", "name": "GST Explanation Bot", "description": "Analyze GST documents and forms"},
            {"id": "resume", "name": "Resume Reviewer", "description": "Score and improve resumes"},
            {"id": "rti", "name": "RTI Simplifier", "description": "Simplify RTI applications and responses"},
        ],
        "content": [
            {"id": "video_to_reels", "name": "Long Video → Reels", "description": "Extract key moments from YouTube videos"},
            {"id": "tweet_to_carousel", "name": "Tweet → Carousel", "description": "Convert tweets to Instagram carousels"},
            {"id": "blog_to_linkedin", "name": "Blog → LinkedIn Post", "description": "Repurpose blogs as LinkedIn content"},
            {"id": "pdf_to_quiz", "name": "PDF → Quiz", "description": "Generate quizzes from PDF content"},
            {"id": "notes_to_flashcards", "name": "Notes → Flashcards", "description": "Convert notes to study flashcards"},
            {"id": "podcast_to_clips", "name": "Podcast → Clips", "description": "Extract shareable clips from podcasts"},
            {"id": "blog_to_thread", "name": "Blog → Twitter Thread", "description": "Convert blogs to Twitter threads"},
        ],
        "political": [
            {"id": "speech_summarizer", "name": "Politician Speech Summarizer", "description": "Summarize political speeches in Hindi/English"},
            {"id": "narrative", "name": "Political Trend Analyzer", "description": "Analyze political trends and narratives"},
            {"id": "constituency", "name": "Constituency Intelligence", "description": "Deep intelligence on a constituency"},
            {"id": "election_monitor", "name": "Election News Summarizer", "description": "Monitor and summarize election news"},
        ],
        "multilingual": [
            {"id": "translate", "name": "Local Language Translator", "description": "Translate to 20+ languages"},
            {"id": "hindi_news", "name": "Hindi News Converter", "description": "Convert English news to Hindi with TTS script"},
            {"id": "regional_summary", "name": "Regional Language Summarizer", "description": "Summarize in regional Indian languages"},
            {"id": "subtitle_generator", "name": "Subtitle Generator", "description": "Generate translated subtitles"},
            {"id": "multilingual", "name": "Multilingual Content", "description": "Create content in multiple languages at once"},
        ],
        "property": [
            {"id": "listing_analyzer", "name": "Property Listing Analyzer", "description": "Analyze listings for value, ROI, red flags"},
            {"id": "market_intelligence", "name": "Real Estate Market Intel", "description": "Market trends for any Indian city"},
            {"id": "fraud_check", "name": "Property Fraud Detector", "description": "Detect fraud indicators in property documents"},
        ],
    }
