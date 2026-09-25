from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import User
from app.services.connections import get_or_create_user


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    """Phase 1: no login. Everyone is the seeded test user; the id is kept in the signed session cookie."""
    user = await get_or_create_user(session, get_settings().seed_user_email)
    request.session["user_id"] = user.id
    return user


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"
