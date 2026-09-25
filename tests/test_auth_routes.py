"""Route-level checks that need no live provider: state/CSRF, unknown providers, rate limiting."""
import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.core.db as db

    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_sessionmaker", None)
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/t.db")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from sqlalchemy import create_engine
    from app.core.db import Base

    Base.metadata.create_all(create_engine(f"sqlite:///{tmp_path}/t.db"))
    with TestClient(create_app(), follow_redirects=False) as c:
        yield c
    get_settings.cache_clear()


def test_connect_redirects_to_strava_with_state(client):
    r = client.get("/auth/strava/connect")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://www.strava.com/oauth/authorize")
    assert "state=" in loc and "client_id=fake-id" in loc


def test_callback_without_prior_connect_is_rejected(client):
    r = client.get("/auth/strava/callback?code=abc&state=forged")
    assert r.status_code == 400


def test_callback_with_wrong_state_is_rejected(client):
    client.get("/auth/strava/connect")
    r = client.get("/auth/strava/callback?code=abc&state=forged")
    assert r.status_code == 400


def test_trainingpeaks_is_not_implemented(client):
    assert client.get("/auth/trainingpeaks/connect").status_code == 404


def test_repeated_failures_get_rate_limited(client):
    for _ in range(rate_limit.MAX_FAILURES):
        assert client.get("/auth/strava/callback?code=x&state=y").status_code == 400
    assert client.get("/auth/strava/callback?code=x&state=y").status_code == 429


def test_intervals_connect_redirects_with_state_and_scope(client):
    r = client.get("/auth/intervals_icu/connect")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://intervals.icu/oauth/authorize")
    assert "state=" in loc and "client_id=fake-intervals-id" in loc and "scope=" in loc


def test_intervals_callback_with_forged_state_is_rejected(client):
    client.get("/auth/intervals_icu/connect")
    assert client.get("/auth/intervals_icu/callback?code=abc&state=forged").status_code == 400
