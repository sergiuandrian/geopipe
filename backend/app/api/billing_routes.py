from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_routes import require_user
from app.api.deps import require_project_soft
from app.core.database import get_db
from app.models import ApiKey, Project, User
from app.services import auth as auth_service
from app.services import billing as billing_service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
async def list_plans() -> dict:
    """Public plan catalog."""
    return {
        "plans": billing_service.plan_catalog(),
        "stripe_configured": billing_service.stripe_configured(),
    }


@router.get("/usage")
async def get_usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    project_auth: Annotated[tuple[Project, ApiKey | None], Depends(require_project_soft)],
) -> dict:
    """Usage dashboard payload for the current project."""
    project, _ = project_auth
    summary = await billing_service.usage_summary(db, project)
    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "plan": project.plan,
            "has_subscription": bool(project.stripe_subscription_id),
        },
        "usage": summary,
        "plans": billing_service.plan_catalog(),
        "stripe_configured": billing_service.stripe_configured(),
    }


@router.post("/checkout")
async def create_checkout(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> dict:
    """Start Stripe Checkout for the Pro plan."""
    project = await auth_service.get_user_project(db, user)
    return await billing_service.create_checkout_session(db, project, user.email)


@router.post("/portal")
async def create_portal(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> dict:
    """Open the Stripe customer portal for subscription management."""
    project = await auth_service.get_user_project(db, user)
    return await billing_service.create_portal_session(db, project)


@router.post("/dev-upgrade")
async def local_dev_upgrade(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> dict:
    """Upgrade to Pro without Stripe (local/dev only)."""
    project = await auth_service.get_user_project(db, user)
    project = await billing_service.dev_upgrade(db, project)
    usage = await billing_service.usage_summary(db, project)
    return {
        "project": {"id": project.id, "name": project.name, "plan": project.plan},
        "usage": usage,
        "mode": "dev",
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict:
    """Receive Stripe webhook events."""
    payload = await request.body()
    return await billing_service.handle_stripe_webhook(db, payload, stripe_signature)
