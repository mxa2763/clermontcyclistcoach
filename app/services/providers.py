"""Per-provider OAuth specifics. Everything provider-shaped lives here; routers stay generic."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings
from app.core.security import decrypt_token, encrypt_token
from app.models import ConnectedAccount, Provider

logger = logging.getLogger("ccc.providers")

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_DEAUTHORIZE_URL = "https://www.strava.com/oauth/deauthorize"
STRAVA_SCOPES = "read,activity:read_all,profile:read_all"

# Intervals.icu (verified against the forum OAuth thread; docs are thin). No refresh tokens, no expiry.
INTERVALS_AUTHORIZE_URL = "https://intervals.icu/oauth/authorize"
INTERVALS_TOKEN_URL = "https://intervals.icu/api/oauth/token"
INTERVALS_DISCONNECT_URL = "https://intervals.icu/api/v1/disconnect-app"
INTERVALS_SCOPES = "ACTIVITY:READ,CALENDAR:WRITE,WELLNESS:READ"

# Refresh when the token has less than this long left.
REFRESH_SKEW_SECONDS = 300

oauth = OAuth()


@dataclass
class TokenResult:
    """Provider-normalised outcome of a code exchange."""
    athlete_id: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: str | None


def register_providers() -> None:
    s = get_settings()
    oauth.register(
        name=Provider.strava.value,
        client_id=s.strava_client_id,
        client_secret=s.strava_client_secret,
        authorize_url=STRAVA_AUTHORIZE_URL,
        access_token_url=STRAVA_TOKEN_URL,
        client_kwargs={"scope": STRAVA_SCOPES, "token_endpoint_auth_method": "client_secret_post"},
    )
    oauth.register(
        name=Provider.intervals_icu.value,
        client_id=s.intervals_client_id,
        client_secret=s.intervals_client_secret,
        authorize_url=INTERVALS_AUTHORIZE_URL,
        access_token_url=INTERVALS_TOKEN_URL,
        client_kwargs={"scope": INTERVALS_SCOPES, "token_endpoint_auth_method": "client_secret_post"},
    )


def is_configured(provider: Provider) -> bool:
    s = get_settings()
    if provider is Provider.strava:
        return bool(s.strava_client_id and s.strava_client_secret)
    if provider is Provider.intervals_icu:
        return bool(s.intervals_client_id and s.intervals_client_secret)
    return False


def implemented_providers() -> list[Provider]:
    return [Provider.strava, Provider.intervals_icu]


def redirect_uri(provider: Provider) -> str:
    return f"{get_settings().base_url}/auth/{provider.value}/callback"


def normalise_token(provider: Provider, token: dict, callback_params: dict) -> TokenResult:
    if provider is Provider.strava:
        # Strava's token response has no scope field; the granted scopes arrive on the callback query
        # (and the user may have unticked some on the consent screen).
        return TokenResult(
            athlete_id=str(token["athlete"]["id"]),
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            expires_at=datetime.fromtimestamp(token["expires_at"], tz=timezone.utc),
            scopes=callback_params.get("scope"),
        )
    if provider is Provider.intervals_icu:
        # Response: {token_type, access_token, scope, athlete: {id, name}}. No refresh token or expiry is
        # documented; if that ever changes, keep them so the refresh path below picks them up.
        expires_at = token.get("expires_at")
        return TokenResult(
            athlete_id=str(token["athlete"]["id"]),
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None,
            scopes=token.get("scope"),
        )
    raise NotImplementedError(provider)


async def refresh_account_tokens(account: ConnectedAccount) -> tuple[str, str | None, datetime | None]:
    """Refresh via the provider. Returns (access_token, refresh_token, expires_at)."""
    if account.provider is Provider.strava:
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": s.strava_client_id,
                    "client_secret": s.strava_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": decrypt_token(account.refresh_token_encrypted),
                },
            )
        resp.raise_for_status()
        body = resp.json()
        # Strava rotates the refresh token; always store the new one.
        return (
            body["access_token"],
            body.get("refresh_token"),
            datetime.fromtimestamp(body["expires_at"], tz=timezone.utc),
        )
    if account.provider is Provider.intervals_icu:
        # Defensive only: Intervals.icu is documented as issuing non-expiring tokens, so this shouldn't run.
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                INTERVALS_TOKEN_URL,
                data={
                    "client_id": s.intervals_client_id,
                    "client_secret": s.intervals_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": decrypt_token(account.refresh_token_encrypted),
                },
            )
        resp.raise_for_status()
        body = resp.json()
        expires_in = body.get("expires_in")
        return (
            body["access_token"],
            body.get("refresh_token"),
            datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None,
        )
    raise NotImplementedError(account.provider)


async def revoke_at_provider(account: ConnectedAccount, access_token: str) -> None:
    """Best-effort remote revoke. Raises on failure; caller decides what to do."""
    if account.provider is Provider.strava:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(STRAVA_DEAUTHORIZE_URL, data={"access_token": access_token})
        resp.raise_for_status()
        return
    if account.provider is Provider.intervals_icu:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                INTERVALS_DISCONNECT_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
        resp.raise_for_status()
        return
    raise NotImplementedError(account.provider)
