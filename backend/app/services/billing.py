from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Project, UsageEvent

PLAN_CATALOG = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_monthly_usd": 0,
        "features": ["GeoPackage / DuckDB / SpatiaLite", "Feature + MVT APIs", "MCP agent tools"],
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_monthly_usd": 29,
        "features": [
            "Everything in Free",
            "Higher request limits",
            "Priority agent connectors",
            "Stripe billing portal",
        ],
    },
}


def plan_limit(plan: str) -> int:
    """Return the monthly request limit for a plan."""
    settings = get_settings()
    if plan == "pro":
        return settings.pro_request_limit
    return settings.free_request_limit


def plan_catalog() -> list[dict[str, Any]]:
    """Return public plan catalog with configured limits."""
    return [
        {**PLAN_CATALOG["free"], "request_limit": plan_limit("free")},
        {**PLAN_CATALOG["pro"], "request_limit": plan_limit("pro")},
    ]


def configure_stripe() -> None:
    """Apply Stripe API key from settings when present."""
    settings = get_settings()
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key


async def usage_summary(db: AsyncSession, project: Project) -> dict[str, Any]:
    """Aggregate usage for a project and compare against plan limits."""
    total_result = await db.execute(
        select(func.coalesce(func.sum(UsageEvent.units), 0)).where(UsageEvent.project_id == project.id)
    )
    used = int(total_result.scalar_one())
    limit = plan_limit(project.plan)
    by_endpoint_result = await db.execute(
        select(UsageEvent.endpoint, func.coalesce(func.sum(UsageEvent.units), 0))
        .where(UsageEvent.project_id == project.id)
        .group_by(UsageEvent.endpoint)
        .order_by(func.coalesce(func.sum(UsageEvent.units), 0).desc())
    )
    by_endpoint = [{"endpoint": endpoint, "units": int(units)} for endpoint, units in by_endpoint_result.all()]
    return {
        "requests": used,
        "limit": limit,
        "remaining": max(limit - used, 0),
        "percent": round((used / limit) * 100, 1) if limit else 0,
        "plan": project.plan,
        "by_endpoint": by_endpoint,
    }


async def enforce_plan_limit(db: AsyncSession, project: Project) -> None:
    """Raise 402 when the project has exhausted its plan quota."""
    summary = await usage_summary(db, project)
    if summary["requests"] >= summary["limit"]:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Plan limit reached ({summary['requests']}/{summary['limit']} requests on '{project.plan}'). "
                "Upgrade to Pro to continue."
            ),
        )


def stripe_configured() -> bool:
    """Return True when Stripe secret key is present."""
    return bool(get_settings().stripe_secret_key)


async def ensure_stripe_customer(db: AsyncSession, project: Project, email: str) -> str:
    """Create or return a Stripe customer id for the project."""
    if project.stripe_customer_id:
        return project.stripe_customer_id
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    configure_stripe()
    customer = stripe.Customer.create(
        email=email,
        name=project.name,
        metadata={"project_id": project.id},
    )
    project.stripe_customer_id = customer["id"]
    await db.commit()
    await db.refresh(project)
    return project.stripe_customer_id


async def create_checkout_session(db: AsyncSession, project: Project, email: str) -> dict[str, str]:
    """Create a Stripe Checkout session for the Pro plan."""
    settings = get_settings()
    if not stripe_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_PRO, "
                "or use /v1/billing/dev-upgrade locally."
            ),
        )
    if not settings.stripe_price_pro:
        raise HTTPException(status_code=503, detail="STRIPE_PRICE_PRO is not configured")

    customer_id = await ensure_stripe_customer(db, project, email)
    configure_stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_pro, "quantity": 1}],
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        client_reference_id=project.id,
        metadata={"project_id": project.id},
        subscription_data={"metadata": {"project_id": project.id}},
    )
    return {"checkout_url": session["url"], "session_id": session["id"]}


async def create_portal_session(db: AsyncSession, project: Project) -> dict[str, str]:
    """Create a Stripe Customer Portal session."""
    settings = get_settings()
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    if not project.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on this project")

    configure_stripe()
    session = stripe.billing_portal.Session.create(
        customer=project.stripe_customer_id,
        return_url=settings.stripe_success_url,
    )
    return {"portal_url": session["url"]}


async def apply_subscription(
    db: AsyncSession,
    *,
    project_id: str,
    customer_id: str | None,
    subscription_id: str | None,
    plan: str,
    status: str | None = None,
) -> Project | None:
    """Update project billing fields from a Stripe subscription event."""
    project = await db.get(Project, project_id)
    if not project:
        return None
    if customer_id:
        project.stripe_customer_id = customer_id
    if subscription_id:
        project.stripe_subscription_id = subscription_id
    project.plan = plan if status in {None, "active", "trialing"} else "free"
    if status in {"canceled", "unpaid", "incomplete_expired"}:
        project.plan = "free"
        project.stripe_subscription_id = None
    project.plan_updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)
    return project


async def handle_stripe_webhook(db: AsyncSession, payload: bytes, signature: str | None) -> dict[str, str]:
    """Verify and process Stripe webhook events."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is not configured")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook: {exc}") from exc

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        project_id = data.get("client_reference_id") or (data.get("metadata") or {}).get("project_id")
        if project_id:
            await apply_subscription(
                db,
                project_id=project_id,
                customer_id=data.get("customer"),
                subscription_id=data.get("subscription"),
                plan="pro",
                status="active",
            )
    elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        metadata = data.get("metadata") or {}
        project_id = metadata.get("project_id")
        if not project_id and data.get("customer"):
            result = await db.execute(
                select(Project).where(Project.stripe_customer_id == data["customer"]).limit(1)
            )
            project = result.scalar_one_or_none()
            project_id = project.id if project else None
        if project_id:
            status = data.get("status")
            plan = "pro" if status in {"active", "trialing"} else "free"
            await apply_subscription(
                db,
                project_id=project_id,
                customer_id=data.get("customer"),
                subscription_id=data.get("id"),
                plan=plan,
                status=status,
            )

    return {"received": True, "type": event_type}


async def dev_upgrade(db: AsyncSession, project: Project) -> Project:
    """Local-only Pro upgrade when Stripe is not configured."""
    if stripe_configured():
        raise HTTPException(status_code=400, detail="Use Stripe Checkout when Stripe is configured")
    project.plan = "pro"
    project.plan_updated_at = datetime.now(timezone.utc)
    project.stripe_subscription_id = f"dev_sub_{project.id}"
    await db.commit()
    await db.refresh(project)
    return project
