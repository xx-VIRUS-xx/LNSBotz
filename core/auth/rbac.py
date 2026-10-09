from functools import wraps
from fastapi import HTTPException
from core.db.models import User, PlanTier


PLAN_LIMITS = {
    PlanTier.FREE: {
        "bots": 1,
        "requests_per_day": 50,
        "monitoring_sources": 2,
        "content_jobs_per_day": 5,
    },
    PlanTier.STARTER: {
        "bots": 5,
        "requests_per_day": 500,
        "monitoring_sources": 10,
        "content_jobs_per_day": 50,
    },
    PlanTier.PRO: {
        "bots": 20,
        "requests_per_day": 2000,
        "monitoring_sources": 50,
        "content_jobs_per_day": 200,
    },
    PlanTier.BUSINESS: {
        "bots": 100,
        "requests_per_day": 10000,
        "monitoring_sources": 500,
        "content_jobs_per_day": 1000,
    },
}

PLAN_PRICES_USD = {
    PlanTier.FREE: 0,
    PlanTier.STARTER: 9,
    PlanTier.PRO: 29,
    PlanTier.BUSINESS: 99,
}


def require_plan(*allowed_plans: PlanTier):
    """Dependency factory: raise 403 if user's plan is not in allowed_plans."""
    def dependency(current_user: User):
        if current_user.plan not in allowed_plans:
            min_plan = allowed_plans[0]
            raise HTTPException(
                status_code=403,
                detail=f"This feature requires {min_plan.value} plan or higher. "
                       f"Upgrade at /billing/upgrade"
            )
        return current_user
    return dependency


def get_plan_limit(user: User, key: str) -> int:
    return PLAN_LIMITS.get(user.plan, PLAN_LIMITS[PlanTier.FREE]).get(key, 0)
