import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token, encrypt_token
from app.models import ConnectedAccount
from app.services import providers
from app.services.connections import as_utc, utcnow

logger = logging.getLogger("ccc.tokens")


class ReauthRequired(Exception):
    """Token is expired and cannot be refreshed; the user must reconnect."""


def needs_refresh(account: ConnectedAccount) -> bool:
    # token_expires_at is NULL for non-expiring tokens (Intervals.icu): never refresh those.
    expires_at = as_utc(account.token_expires_at)
    if expires_at is None:
        return False
    return expires_at - utcnow() <= timedelta(seconds=providers.REFRESH_SKEW_SECONDS)


async def get_valid_access_token(session: AsyncSession, account: ConnectedAccount) -> str:
    """Return a usable plaintext access token, refreshing and persisting new tokens if near expiry."""
    if not needs_refresh(account):
        return decrypt_token(account.access_token_encrypted)

    if not account.refresh_token_encrypted:
        raise ReauthRequired(f"{account.provider.value} token expired and no refresh token stored")

    try:
        access, refresh, expires_at = await providers.refresh_account_tokens(account)
    except Exception as exc:
        logger.warning("token refresh failed for %s account %s: %s", account.provider.value, account.id, exc)
        raise ReauthRequired("token refresh failed") from exc

    account.access_token_encrypted = encrypt_token(access)
    if refresh:
        account.refresh_token_encrypted = encrypt_token(refresh)
    account.token_expires_at = expires_at
    await session.commit()
    return access
