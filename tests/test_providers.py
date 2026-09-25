from app.models import Provider
from app.services.providers import normalise_token


def test_intervals_token_has_no_refresh_or_expiry():
    token = {
        "token_type": "Bearer",
        "access_token": "tok",
        "scope": "ACTIVITY:READ,CALENDAR:WRITE",
        "athlete": {"id": "i12345", "name": "Test"},
    }
    r = normalise_token(Provider.intervals_icu, token, {})
    assert r.athlete_id == "i12345"
    assert r.refresh_token is None and r.expires_at is None
    assert r.scopes == "ACTIVITY:READ,CALENDAR:WRITE"


def test_strava_scopes_come_from_callback_query():
    token = {"access_token": "a", "refresh_token": "r", "expires_at": 2_000_000_000, "athlete": {"id": 42}}
    r = normalise_token(Provider.strava, token, {"scope": "read,activity:read_all"})
    assert r.athlete_id == "42"
    assert r.scopes == "read,activity:read_all"
    assert r.expires_at is not None
