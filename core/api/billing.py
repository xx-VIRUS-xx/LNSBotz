"""
Billing — Razorpay (India / UPI) + PayPal (international).
India users pay via Razorpay (UPI, cards, netbanking).
International users pay via PayPal.
"""
import hmac
import hashlib
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.db import get_db, User
from core.db.models import PlanTier
from core.auth import get_current_user_flexible
from core.config import settings
from core.observability import logger

router = APIRouter(prefix="/billing", tags=["Billing"])

PLAN_PRICES_INR = {
    PlanTier.STARTER: 750,      # ~$9 USD
    PlanTier.PRO: 2400,         # ~$29 USD
    PlanTier.BUSINESS: 8200,    # ~$99 USD
}

PLAN_PRICES_USD = {
    PlanTier.STARTER: 9,
    PlanTier.PRO: 29,
    PlanTier.BUSINESS: 99,
}

PLAN_FEATURES = {
    PlanTier.FREE:     {"bots": 1,   "requests_per_day": 50,    "features": ["1 bot", "50 req/day", "Basic monitoring"]},
    PlanTier.STARTER:  {"bots": 5,   "requests_per_day": 500,   "features": ["5 bots", "500 req/day", "All bot types", "Telegram + Email alerts"]},
    PlanTier.PRO:      {"bots": 20,  "requests_per_day": 2000,  "features": ["20 bots", "2000 req/day", "Priority models", "Webhooks", "Priority support"]},
    PlanTier.BUSINESS: {"bots": 100, "requests_per_day": 10000, "features": ["100 bots", "10K req/day", "White-label", "API access", "Dedicated support"]},
}


# ── Plans ─────────────────────────────────────────────────────────────────────

@router.get("/plans", summary="View all plans and pricing")
async def get_plans():
    return {
        "plans": [
            {
                "name": tier.value.title(),
                "tier": tier.value,
                "price_inr": PLAN_PRICES_INR.get(tier, 0),
                "price_usd": PLAN_PRICES_USD.get(tier, 0),
                **PLAN_FEATURES[tier],
            }
            for tier in PlanTier
        ]
    }


@router.get("/usage", summary="View current plan and usage limits")
async def get_usage(user: User = Depends(get_current_user_flexible)):
    from core.auth.rbac import PLAN_LIMITS
    return {
        "plan": user.plan.value,
        "price_inr": PLAN_PRICES_INR.get(user.plan, 0),
        "price_usd": PLAN_PRICES_USD.get(user.plan, 0),
        "limits": PLAN_LIMITS[user.plan],
        "upgrade_url": "/api/v1/billing/plans",
    }


# ── Razorpay (India) ──────────────────────────────────────────────────────────

class RazorpayOrderRequest(BaseModel):
    plan: PlanTier
    currency: str = "INR"


@router.post("/razorpay/order", summary="Create Razorpay order (India / UPI)")
async def create_razorpay_order(
    req: RazorpayOrderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_id or not key_secret:
        raise HTTPException(503, "Razorpay not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env")

    amount_inr = PLAN_PRICES_INR.get(req.plan)
    if not amount_inr:
        raise HTTPException(400, "Invalid plan")

    payload = {
        "amount": amount_inr * 100,  # Razorpay expects paise
        "currency": req.currency,
        "receipt": f"user_{user.id}_{req.plan.value}",
        "notes": {"user_id": str(user.id), "plan": req.plan.value, "email": user.email},
    }
    async with httpx.AsyncClient(auth=(key_id, key_secret), timeout=15) as client:
        resp = await client.post("https://api.razorpay.com/v1/orders", json=payload)
        resp.raise_for_status()

    order = resp.json()
    return {
        "order_id": order["id"],
        "amount": amount_inr,
        "currency": req.currency,
        "key_id": key_id,
        "plan": req.plan.value,
        "prefill": {"email": user.email},
    }


@router.post("/razorpay/verify", summary="Verify Razorpay payment and upgrade plan")
async def verify_razorpay_payment(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    body = await request.json()
    razorpay_order_id = body.get("razorpay_order_id", "")
    razorpay_payment_id = body.get("razorpay_payment_id", "")
    razorpay_signature = body.get("razorpay_signature", "")
    plan_value = body.get("plan", "")

    key_secret = settings.RAZORPAY_KEY_SECRET
    expected_sig = hmac.new(
        key_secret.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, razorpay_signature):
        raise HTTPException(400, "Invalid payment signature")

    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one_or_none()
    if db_user:
        db_user.plan = PlanTier(plan_value)
        logger.info("plan_upgraded_razorpay", user_id=str(user.id), plan=plan_value, payment_id=razorpay_payment_id)

    return {"status": "success", "plan": plan_value, "message": f"Upgraded to {plan_value} plan!"}


# ── PayPal (International) ────────────────────────────────────────────────────

async def _get_paypal_token() -> str:
    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    base = "https://api-m.sandbox.paypal.com" if settings.PAYPAL_SANDBOX else "https://api-m.paypal.com"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
    return resp.json()["access_token"]


class PayPalOrderRequest(BaseModel):
    plan: PlanTier
    return_url: str
    cancel_url: str


@router.post("/paypal/order", summary="Create PayPal order (International)")
async def create_paypal_order(
    req: PayPalOrderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    client_id = settings.PAYPAL_CLIENT_ID
    if not client_id:
        raise HTTPException(503, "PayPal not configured. Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to .env")

    amount_usd = PLAN_PRICES_USD.get(req.plan)
    if not amount_usd:
        raise HTTPException(400, "Invalid plan")

    token = await _get_paypal_token()
    base = "https://api-m.sandbox.paypal.com" if settings.PAYPAL_SANDBOX else "https://api-m.paypal.com"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": str(amount_usd)},
            "description": f"LNS Botz — {req.plan.value.title()} Plan",
            "custom_id": f"{user.id}|{req.plan.value}",
        }],
        "application_context": {
            "return_url": req.return_url,
            "cancel_url": req.cancel_url,
            "brand_name": "LNS Botz",
            "user_action": "PAY_NOW",
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/v2/checkout/orders",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    order = resp.json()
    approve_url = next((l["href"] for l in order.get("links", []) if l["rel"] == "approve"), None)
    return {
        "order_id": order["id"],
        "approve_url": approve_url,
        "amount_usd": amount_usd,
        "plan": req.plan.value,
    }


@router.post("/paypal/capture/{order_id}", summary="Capture PayPal payment and upgrade plan")
async def capture_paypal_payment(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_flexible),
):
    token = await _get_paypal_token()
    base = "https://api-m.sandbox.paypal.com" if settings.PAYPAL_SANDBOX else "https://api-m.paypal.com"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/v2/checkout/orders/{order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    capture = resp.json()
    if capture.get("status") != "COMPLETED":
        raise HTTPException(400, f"Payment not completed: {capture.get('status')}")

    custom_id = capture["purchase_units"][0].get("custom_id", "")
    plan_value = custom_id.split("|")[1] if "|" in custom_id else None
    if plan_value:
        result = await db.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.plan = PlanTier(plan_value)
            logger.info("plan_upgraded_paypal", user_id=str(user.id), plan=plan_value, order_id=order_id)

    return {"status": "success", "plan": plan_value, "message": f"Upgraded to {plan_value} plan!"}
