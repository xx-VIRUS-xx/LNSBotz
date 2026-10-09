"""
LNS Botz — Main FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from core.config import settings
from core.observability import setup_logging, logger
from core.db import engine, Base
from core.api import auth_router, billing_router, google_oauth_router
from bots.monitoring import router as monitoring_router
from bots.content import router as content_router
from bots.telegram import router as telegram_router
from bots.business import router as business_router
from products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("startup", env=settings.ENV, app=settings.APP_NAME)

    # Create DB tables (use Alembic migrations in production)
    if settings.ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("db_tables_ensured")

    yield

    logger.info("shutdown")
    await engine.dispose()


app = FastAPI(
    title="LNS Botz — AI Utility Ecosystem",
    description="""
## AI Utility Ecosystem — 30+ Products, One Platform

### Intelligence Products
Competitor tracker, Political narrative, Reddit sentiment, Tender alerts, Stock news, Job monitor, X trends, Election monitor

### Document Intelligence
Invoice analyzer, Legal notice simplifier, GST bot, Resume reviewer, RTI simplifier, Property documents

### Content Transformation
Video → Reels, Blog → LinkedIn, PDF → Quiz, Notes → Flashcards, Podcast → Clips, Tweet → Carousel

### Political Intelligence
Speech summarizer, Narrative tracker, Constituency intelligence, Election monitor

### Multilingual
Translate to 20+ languages, Hindi news converter, Regional summarizer, Subtitle generator

### Real Estate
Property listing analyzer, Market intelligence, Fraud detection

### Authentication
Use `Bearer <token>` or `X-API-Key: <key>` header.
    """,
    version="1.0.0",
    lifespan=lifespan,
    # API explorer is enabled only in development. Disabled in production
    # so the full API surface isn't exposed publicly.
    docs_url="/docs" if settings.ENV == "development" else None,
    redoc_url="/redoc" if settings.ENV == "development" else None,
    openapi_url="/openapi.json" if settings.ENV == "development" else None,
)

# ── Middleware ────────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    "https://lnsbotz.latenightstack.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "development" else ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    from core.cache import rate_limiter
    from fastapi.responses import JSONResponse

    # Extract user identifier from API key or skip (JWT handled per-route)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        identifier = api_key[:10]
        allowed = await rate_limiter.is_allowed(identifier, settings.RATE_LIMIT_PER_MINUTE, 60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Upgrade your plan for higher limits."},
            )
    return await call_next(request)


# ── Routes ────────────────────────────────────────────────────────────────────

PREFIX = settings.API_V1_PREFIX

app.include_router(auth_router, prefix=PREFIX)
app.include_router(google_oauth_router, prefix=PREFIX)
app.include_router(billing_router, prefix=PREFIX)
app.include_router(monitoring_router, prefix=PREFIX)
app.include_router(content_router, prefix=PREFIX)
app.include_router(telegram_router, prefix=PREFIX)
app.include_router(business_router, prefix=PREFIX)
app.include_router(products_router, prefix=PREFIX)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "1.0.0", "env": settings.ENV}


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("frontend/index.html")


@app.get("/app", include_in_schema=False)
async def app_workspace():
    # Same SPA; the page detects the /app path and shows the dashboard directly
    return FileResponse("frontend/index.html")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
