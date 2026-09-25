import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    fernet_key: str
    session_secret: str
    database_url: str
    base_url: str
    seed_user_email: str
    strava_client_id: str
    strava_client_secret: str
    intervals_client_id: str
    intervals_client_secret: str


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value or value.startswith("REPLACE_ME"):
        raise RuntimeError(f"Environment variable {name} is not set (see .env.example)")
    return value


@lru_cache
def get_settings() -> Settings:
    return Settings(
        fernet_key=_required("FERNET_KEY"),
        session_secret=_required("SESSION_SECRET"),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ccc.db"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        seed_user_email=os.getenv("SEED_USER_EMAIL", "test@example.com"),
        strava_client_id=os.getenv("STRAVA_CLIENT_ID", ""),
        strava_client_secret=os.getenv("STRAVA_CLIENT_SECRET", ""),
        intervals_client_id=os.getenv("INTERVALS_CLIENT_ID", ""),
        intervals_client_secret=os.getenv("INTERVALS_CLIENT_SECRET", ""),
    )
