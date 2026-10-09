"""Auth endpoints — register, login, API key management."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.db import get_db, User, APIKey
from core.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    generate_api_key, get_current_user_flexible,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me", summary="Current user profile + plan + usage")
async def get_me(user: User = Depends(get_current_user_flexible)):
    from core.auth.rbac import PLAN_LIMITS
    from core.cache import Cache
    from datetime import datetime, timezone

    limits = PLAN_LIMITS.get(user.plan, {})
    daily_limit = limits.get("requests_per_day", 0)

    # Count today's requests from Redis usage counter
    usage_cache = Cache(prefix="metrics", ttl=86400)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    used = 0
    try:
        from core.cache import get_redis
        r = await get_redis()
        # sum all per-operation counters for this user today
        keys = await r.keys(f"metrics:usage:requests:{user.id}:*")
        for k in keys:
            v = await r.get(k)
            used += int(v or 0)
    except Exception:
        used = 0

    return {
        "email": user.email,
        "full_name": user.full_name,
        "plan": user.plan.value,
        "limits": limits,
        "usage": {
            "requests_today": used,
            "requests_limit": daily_limit,
            "bots_limit": limits.get("bots", 0),
        },
    }


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", summary="Create a new account")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer", "user_id": str(user.id)}


@router.post("/login", summary="Get access token")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account inactive")

    return {
        "access_token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
        "plan": user.plan.value,
    }


class CreateAPIKeyRequest(BaseModel):
    name: str


@router.post("/api-keys", summary="Create an API key")
async def create_api_key(
    req: CreateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    raw, key_hash, prefix = generate_api_key()
    key_record = APIKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=prefix,
        name=req.name,
    )
    db.add(key_record)
    await db.flush()
    return {
        "api_key": raw,
        "prefix": prefix,
        "name": req.name,
        "warning": "Save this key — it will NOT be shown again",
    }


@router.get("/api-keys", summary="List API keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(select(APIKey).where(APIKey.user_id == user.id))
    keys = result.scalars().all()
    return [
        {"id": str(k.id), "name": k.name, "prefix": k.key_prefix, "active": k.is_active,
         "requests": k.requests_count}
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", summary="Revoke an API key")
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    key.is_active = False
    return {"status": "revoked"}
