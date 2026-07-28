from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ApiKey, Project, User
from app.services import ingest

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, user_id: str, email: str) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": user_id, "email": email, "exp": expire, "typ": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return payload


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Lookup a user by normalized email."""
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def create_user_with_project(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    name: str | None = None,
) -> tuple[User, Project, str]:
    """Register a user, create their free project, and issue an API key."""
    normalized = email.lower().strip()
    if await get_user_by_email(db, normalized):
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        name=(name or normalized.split("@")[0])[:120],
    )
    db.add(user)
    await db.flush()

    project = Project(
        name=f"{user.name}'s workspace",
        plan="free",
        owner_user_id=user.id,
    )
    db.add(project)
    await db.flush()

    raw, prefix, hashed = ingest.generate_api_key()
    db.add(ApiKey(project_id=project.id, name="default", key_prefix=prefix, key_hash=hashed))
    await db.commit()
    await db.refresh(user)
    await db.refresh(project)
    return user, project, raw


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Validate email/password credentials."""
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user


async def get_user_project(db: AsyncSession, user: User) -> Project:
    """Return the primary project owned by a user, creating one if missing."""
    result = await db.execute(
        select(Project).where(Project.owner_user_id == user.id).order_by(Project.created_at.asc()).limit(1)
    )
    project = result.scalar_one_or_none()
    if project:
        return project

    project = Project(name=f"{user.name}'s workspace", plan="free", owner_user_id=user.id)
    db.add(project)
    await db.flush()
    raw, prefix, hashed = ingest.generate_api_key()
    db.add(ApiKey(project_id=project.id, name="default", key_prefix=prefix, key_hash=hashed))
    await db.commit()
    await db.refresh(project)
    return project


def user_to_dict(user: User) -> dict:
    """Serialize a user for API responses."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
