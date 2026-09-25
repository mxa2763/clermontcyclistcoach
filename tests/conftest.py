import os

from cryptography.fernet import Fernet

# Must be set before app modules read settings.
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["SESSION_SECRET"] = "test-session-secret"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["STRAVA_CLIENT_ID"] = "fake-id"
os.environ["STRAVA_CLIENT_SECRET"] = "fake-secret"
os.environ["INTERVALS_CLIENT_ID"] = "fake-intervals-id"
os.environ["INTERVALS_CLIENT_SECRET"] = "fake-intervals-secret"

import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import rate_limit  # noqa: E402
from app.core.db import Base  # noqa: E402
import app.models  # noqa: E402,F401


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limit():
    rate_limit.reset()
