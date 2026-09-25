from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import decrypt_token
from app.models import ConnectedAccount, Provider, User
from app.services.connections import (
    get_active_connection,
    revoke_connection_locally,
    upsert_connection,
    utcnow,
)
from app.services.tokens import get_valid_access_token, needs_refresh, ReauthRequired


async def _user(session, email="a@example.com") -> User:
    u = User(email=email)
    session.add(u)
    await session.commit()
    return u


def _kwargs(user, **over):
    base = dict(
        user_id=user.id,
        provider=Provider.strava,
        provider_athlete_id="123",
        access_token="access-1",
        refresh_token="refresh-1",
        token_expires_at=utcnow() + timedelta(hours=6),
        scopes_granted="read,activity:read_all",
    )
    return {**base, **over}


async def test_upsert_creates_and_stores_only_ciphertext(session):
    user = await _user(session)
    acct = await upsert_connection(session, **_kwargs(user))
    assert acct.access_token_encrypted != "access-1"
    assert decrypt_token(acct.access_token_encrypted) == "access-1"
    assert decrypt_token(acct.refresh_token_encrypted) == "refresh-1"


async def test_upsert_twice_updates_same_row(session):
    user = await _user(session)
    first = await upsert_connection(session, **_kwargs(user))
    second = await upsert_connection(session, **_kwargs(user, access_token="access-2"))
    assert first.id == second.id
    rows = (await session.execute(select(ConnectedAccount))).scalars().all()
    assert len(rows) == 1
    assert decrypt_token(rows[0].access_token_encrypted) == "access-2"


async def test_intervals_style_connection_without_refresh_or_expiry(session):
    user = await _user(session)
    acct = await upsert_connection(
        session,
        **_kwargs(user, provider=Provider.intervals_icu, refresh_token=None, token_expires_at=None),
    )
    assert acct.refresh_token_encrypted is None
    assert not needs_refresh(acct)
    assert await get_valid_access_token(session, acct) == "access-1"


async def test_reconnect_after_revoke_creates_new_active_row(session):
    user = await _user(session)
    acct = await upsert_connection(session, **_kwargs(user))
    await revoke_connection_locally(session, acct)
    assert acct.revoked_at is not None
    assert decrypt_token(acct.access_token_encrypted) == ""
    assert await get_active_connection(session, user.id, Provider.strava) is None

    again = await upsert_connection(session, **_kwargs(user))
    assert again.id != acct.id
    assert again.revoked_at is None


async def test_same_athlete_cannot_be_active_on_two_users(session):
    u1, u2 = await _user(session, "a@example.com"), await _user(session, "b@example.com")
    await upsert_connection(session, **_kwargs(u1))
    with pytest.raises(IntegrityError):
        await upsert_connection(session, **_kwargs(u2))


async def test_at_most_one_active_row_per_user_provider(session):
    user = await _user(session)
    await upsert_connection(session, **_kwargs(user))
    session.add(
        ConnectedAccount(
            user_id=user.id, provider=Provider.strava, provider_athlete_id="999",
            access_token_encrypted="x",
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_needs_refresh_window(session):
    user = await _user(session)
    fresh = await upsert_connection(session, **_kwargs(user))
    assert not needs_refresh(fresh)
    fresh.token_expires_at = utcnow() + timedelta(seconds=60)
    assert needs_refresh(fresh)
    fresh.token_expires_at = utcnow() - timedelta(hours=1)
    assert needs_refresh(fresh)


async def test_expired_token_is_refreshed_and_rotated(session, monkeypatch):
    user = await _user(session)
    acct = await upsert_connection(session, **_kwargs(user, token_expires_at=utcnow() - timedelta(hours=1)))

    async def fake_refresh(account):
        return "access-new", "refresh-new", utcnow() + timedelta(hours=6)

    monkeypatch.setattr("app.services.providers.refresh_account_tokens", fake_refresh)
    assert await get_valid_access_token(session, acct) == "access-new"
    assert decrypt_token(acct.access_token_encrypted) == "access-new"
    assert decrypt_token(acct.refresh_token_encrypted) == "refresh-new"
    assert not needs_refresh(acct)


async def test_failed_refresh_requires_reauth(session, monkeypatch):
    user = await _user(session)
    acct = await upsert_connection(session, **_kwargs(user, token_expires_at=utcnow() - timedelta(hours=1)))

    async def boom(account):
        raise RuntimeError("provider down")

    monkeypatch.setattr("app.services.providers.refresh_account_tokens", boom)
    with pytest.raises(ReauthRequired):
        await get_valid_access_token(session, acct)
