from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_token
from app.models import ConnectedAccount, Provider, User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; everything we store is UTC, so re-attach it."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def get_or_create_user(session: AsyncSession, email: str) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email)
        session.add(user)
        await session.commit()
    return user


async def get_active_connection(
    session: AsyncSession, user_id: int, provider: Provider
) -> ConnectedAccount | None:
    stmt = select(ConnectedAccount).where(
        ConnectedAccount.user_id == user_id,
        ConnectedAccount.provider == provider,
        ConnectedAccount.revoked_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_active_connections(session: AsyncSession, user_id: int) -> list[ConnectedAccount]:
    stmt = select(ConnectedAccount).where(
        ConnectedAccount.user_id == user_id, ConnectedAccount.revoked_at.is_(None)
    )
    return list((await session.execute(stmt)).scalars())


async def upsert_connection(
    session: AsyncSession,
    *,
    user_id: int,
    provider: Provider,
    provider_athlete_id: str,
    access_token: str,
    refresh_token: str | None,
    token_expires_at: datetime | None,
    scopes_granted: str | None,
) -> ConnectedAccount:
    """Create or update the user's single active connection for a provider. Tokens are encrypted here."""
    account = await get_active_connection(session, user_id, provider)
    if account is None:
        account = ConnectedAccount(user_id=user_id, provider=provider, connected_at=utcnow())
        session.add(account)
    account.provider_athlete_id = str(provider_athlete_id)
    account.access_token_encrypted = encrypt_token(access_token)
    account.refresh_token_encrypted = encrypt_token(refresh_token) if refresh_token else None
    account.token_expires_at = token_expires_at
    account.scopes_granted = scopes_granted
    await session.commit()
    return account


async def revoke_connection_locally(session: AsyncSession, account: ConnectedAccount) -> None:
    """Mark revoked and drop the stored credentials; the row is kept for history."""
    account.revoked_at = utcnow()
    account.access_token_encrypted = encrypt_token("")
    account.refresh_token_encrypted = None
    account.token_expires_at = None
    await session.commit()
