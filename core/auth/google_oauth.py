"""
Google OAuth 2.0 — Gmail Sign In.
Flow: /auth/google/login → Google consent → /auth/google/callback → JWT issued
"""
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from urllib.parse import urlencode

from core.config import settings
from core.db.base import AsyncSessionLocal
from core.db.models import User
from core.auth.security import create_access_token, create_refresh_token, hash_password
from core.observability import logger
import secrets

router = APIRouter(prefix="/auth", tags=["Auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login", summary="Redirect to Google OAuth consent screen")
async def google_login(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google OAuth not configured")

    state = secrets.token_urlsafe(16)
    # Store state in session cookie for CSRF protection
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    response = RedirectResponse(url)
    response.set_cookie("oauth_state", state, httponly=True, max_age=300, samesite="lax")
    return response


@router.get("/google/callback", summary="Google OAuth callback — issues JWT")
async def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"/?auth_error={error}")

    if not code:
        raise HTTPException(400, "Missing authorization code")

    # Exchange code for tokens
    token_data = await _exchange_code(code)
    if not token_data:
        raise HTTPException(400, "Failed to exchange code for tokens")

    # Get user info from Google
    user_info = await _get_user_info(token_data["access_token"])
    if not user_info or not user_info.get("email"):
        raise HTTPException(400, "Failed to get user info from Google")

    email = user_info["email"]
    full_name = user_info.get("name", "")
    google_id = user_info.get("sub", "")
    avatar = user_info.get("picture", "")

    # Find or create user
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # New user — create account
            user = User(
                email=email,
                hashed_password=hash_password(secrets.token_urlsafe(32)),  # random unusable password
                full_name=full_name,
                is_active=True,
            )
            db.add(user)
            await db.flush()
            logger.info("google_oauth_new_user", email=email)
        else:
            logger.info("google_oauth_existing_user", email=email)

        user_id = str(user.id)
        plan = user.plan.value
        await db.commit()

    access_token = create_access_token(user_id, extra={"email": email, "name": full_name})
    refresh_token = create_refresh_token(user_id)

    # Redirect to frontend with tokens in URL fragment (never in query string)
    frontend_url = (
        f"/?auth=success"
        f"&token={access_token}"
        f"&refresh={refresh_token}"
        f"&plan={plan}"
        f"&name={full_name}"
        f"&email={email}"
    )
    response = RedirectResponse(frontend_url)
    response.delete_cookie("oauth_state")
    return response


@router.get("/google/config", summary="Check if Google OAuth is configured")
async def google_config():
    return {"enabled": bool(settings.GOOGLE_CLIENT_ID)}


async def _exchange_code(code: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("google_token_exchange_failed", error=str(e))
        return None


async def _get_user_info(access_token: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("google_userinfo_failed", error=str(e))
        return None
