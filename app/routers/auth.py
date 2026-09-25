import logging

from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.db import get_session
from app.core.deps import client_key, get_current_user
from app.models import Provider, User
from app.services import providers
from app.services.connections import (
    get_active_connection,
    revoke_connection_locally,
    upsert_connection,
)
from app.services.tokens import get_valid_access_token

logger = logging.getLogger("ccc.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def resolve_provider(provider: str) -> Provider:
    """404 for anything not implemented this phase (including trainingpeaks)."""
    try:
        p = Provider(provider)
    except ValueError:
        raise HTTPException(404, "Unknown provider")
    if p not in providers.implemented_providers():
        raise HTTPException(404, f"Provider '{provider}' is not implemented")
    return p


@router.get("/{provider}/connect")
async def connect(provider: str, request: Request, user: User = Depends(get_current_user)):
    p = resolve_provider(provider)
    if not providers.is_configured(p):
        raise HTTPException(503, f"{p.value} client credentials are not set in .env")
    client = getattr(providers.oauth, p.value)
    # Authlib generates the state, stores it in the signed session, and adds it to the URL.
    return await client.authorize_redirect(request, providers.redirect_uri(p))


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    p = resolve_provider(provider)
    key = client_key(request)
    rate_limit.check_allowed(key)

    params = dict(request.query_params)
    if "error" in params:  # e.g. user clicked "Cancel" on the consent screen
        rate_limit.record_failure(key, f"{p.value} returned error={params['error']}")
        return RedirectResponse(f"/?error={params['error']}")

    client = getattr(providers.oauth, p.value)
    try:
        # Validates the state parameter against the session (CSRF) and exchanges the code.
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        rate_limit.record_failure(key, f"{p.value} OAuth error: {exc.error}")
        raise HTTPException(400, "OAuth callback failed (invalid state or code)")

    result = providers.normalise_token(p, token, params)
    try:
        await upsert_connection(
            session,
            user_id=user.id,
            provider=p,
            provider_athlete_id=result.athlete_id,
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_expires_at=result.expires_at,
            scopes_granted=result.scopes,
        )
    except IntegrityError:
        await session.rollback()
        rate_limit.record_failure(key, f"{p.value} athlete already linked to another user")
        raise HTTPException(409, f"That {p.value} account is already connected to another user")
    return RedirectResponse("/?connected=" + p.value)


@router.post("/{provider}/disconnect")
async def disconnect(
    provider: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    p = resolve_provider(provider)
    account = await get_active_connection(session, user.id, p)
    if account is None:
        raise HTTPException(404, f"No active {p.value} connection")

    remote_revoked = True
    try:
        access = await get_valid_access_token(session, account)
        await providers.revoke_at_provider(account, access)
    except Exception as exc:  # remote revoke is best effort; local revoke always happens
        remote_revoked = False
        logger.warning("remote revoke failed for %s account %s: %s", p.value, account.id, exc)

    await revoke_connection_locally(session, account)
    return {"provider": p.value, "revoked_locally": True, "revoked_at_provider": remote_revoked}
