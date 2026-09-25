from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.models import User
from app.services import providers
from app.services.connections import list_active_connections

router = APIRouter(prefix="/api", tags=["api"])


class ConnectionStatus(BaseModel):
    provider: str
    configured: bool
    connected: bool
    provider_athlete_id: str | None = None
    scopes_granted: str | None = None


class ConnectionsResponse(BaseModel):
    user_email: str
    connections: list[ConnectionStatus]


@router.get("/connections", response_model=ConnectionsResponse)
async def connections(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    active = {a.provider: a for a in await list_active_connections(session, user.id)}
    out = []
    for p in providers.implemented_providers():
        a = active.get(p)
        out.append(
            ConnectionStatus(
                provider=p.value,
                configured=providers.is_configured(p),
                connected=a is not None,
                provider_athlete_id=a.provider_athlete_id if a else None,
                scopes_granted=a.scopes_granted if a else None,
            )
        )
    return ConnectionsResponse(user_email=user.email, connections=out)
