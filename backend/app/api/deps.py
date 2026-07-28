from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import ApiKey, Project, User
from app.services import auth as auth_service
from app.services import billing as billing_service
from app.services import ingest


def project_dependency(*, enforce_limit: bool) -> Callable:
    """Build a FastAPI dependency that resolves project auth with optional quota checks."""

    async def _require_project(
        db: Annotated[AsyncSession, Depends(get_db)],
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[Project, ApiKey | None]:
        """Resolve project from API key or Bearer JWT, with optional bootstrap fallback.

        Auth order:
        1. X-API-Key — machine / agent access
        2. Authorization: Bearer <jwt> — signed-in user dashboard
        3. Local bootstrap default project when AUTH_REQUIRED is false
        """
        project: Project | None = None
        api_key: ApiKey | None = None

        if x_api_key:
            project, api_key = await ingest.authenticate_api_key(db, x_api_key)
        elif authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            payload = auth_service.decode_access_token(token)
            user = await db.get(User, payload["sub"])
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            project = await auth_service.get_user_project(db, user)
            api_key = await ingest.get_project_api_key(db, project.id)
        elif not get_settings().auth_required:
            project = await ingest.ensure_default_project(db)
            api_key = None
        else:
            raise HTTPException(status_code=401, detail="Authentication required (X-API-Key or Bearer token)")

        if enforce_limit:
            await billing_service.enforce_plan_limit(db, project)
        return project, api_key

    return _require_project


require_project = project_dependency(enforce_limit=True)
require_project_soft = project_dependency(enforce_limit=False)
