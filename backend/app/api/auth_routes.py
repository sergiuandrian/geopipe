from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import User
from app.services import auth as auth_service
from app.services import billing as billing_service
from app.services import ingest

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


async def require_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the authenticated user from a Bearer JWT."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = auth_service.decode_access_token(token)
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/signup")
async def signup(payload: SignupRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Create a user account, free project, and first API key."""
    user, project, raw_key = await auth_service.create_user_with_project(
        db,
        email=str(payload.email),
        password=payload.password,
        name=payload.name,
    )
    token = auth_service.create_access_token(user_id=user.id, email=user.email)
    usage = await billing_service.usage_summary(db, project)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": auth_service.user_to_dict(user),
        "project": {
            "id": project.id,
            "name": project.name,
            "plan": project.plan,
        },
        "api_key": raw_key,
        "usage": usage,
        "warning": "Store this API key now. It will not be shown again.",
    }


@router.post("/login")
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Authenticate with email/password and return a JWT."""
    user = await auth_service.authenticate_user(db, str(payload.email), payload.password)
    project = await auth_service.get_user_project(db, user)
    api_key = await ingest.get_project_api_key(db, project.id)
    token = auth_service.create_access_token(user_id=user.id, email=user.email)
    usage = await billing_service.usage_summary(db, project)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": auth_service.user_to_dict(user),
        "project": {
            "id": project.id,
            "name": project.name,
            "plan": project.plan,
        },
        "api_key_prefix": api_key.key_prefix if api_key else None,
        "usage": usage,
    }


@router.get("/me")
async def me(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> dict:
    """Return the current user, project, and usage snapshot."""
    project = await auth_service.get_user_project(db, user)
    api_key = await ingest.get_project_api_key(db, project.id)
    usage = await billing_service.usage_summary(db, project)
    return {
        "user": auth_service.user_to_dict(user),
        "project": {
            "id": project.id,
            "name": project.name,
            "plan": project.plan,
            "stripe_customer_id": project.stripe_customer_id,
            "has_subscription": bool(project.stripe_subscription_id),
        },
        "api_key_prefix": api_key.key_prefix if api_key else None,
        "usage": usage,
        "plans": billing_service.plan_catalog(),
        "stripe_configured": billing_service.stripe_configured(),
    }
