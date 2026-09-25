# ClermontCyclistCoach (CCC) – Phase 1: accounts & OAuth

Backend foundation: connect Strava (and, next, Intervals.icu) via OAuth, with tokens Fernet-encrypted at rest.
No plan generation or workout logic yet. `planned_workouts` and `activity_debriefs` exist as empty tables only.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env        # then edit .env (see below)
uv run alembic upgrade head # creates ccc.db
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000 (use `localhost`, not `127.0.0.1`, so it matches the registered redirect).

Tests: `uv run pytest`

## Configuration (`.env`, never committed)

| Variable | Notes |
|---|---|
| `FERNET_KEY` | `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. **Losing it makes stored tokens unreadable** (users must reconnect). |
| `SESSION_SECRET` | `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | Default `sqlite+aiosqlite:///./ccc.db`. PostgreSQL later: `postgresql+asyncpg://user:pass@host/db` (add `asyncpg`). |
| `BASE_URL` | Default `http://localhost:8000`. Redirect URIs are `{BASE_URL}/auth/{provider}/callback`. |
| `SEED_USER_EMAIL` | Phase 1 has no login; this seeded user is always "current". |
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | From https://www.strava.com/settings/api. Set **Authorization Callback Domain** to `localhost`. |
| `INTERVALS_CLIENT_ID` / `INTERVALS_CLIENT_SECRET` | Issued manually by the Intervals.icu developer. |

## Manually testing the Strava loop

1. Put your Strava credentials in `.env`, restart the server.
2. Open http://localhost:8000 and click **Connect Strava**. You're sent to Strava's consent screen.
3. Approve. Strava redirects to `/auth/strava/callback`, which validates `state`, exchanges the code, encrypts the tokens and saves them, then returns you to `/` showing "connected" with your athlete id and scopes.
4. Check the DB holds ciphertext only: `sqlite3 ccc.db "select provider, provider_athlete_id, substr(access_token_encrypted,1,20) from connected_accounts;"` (values start with `gAAAA`).
5. Click **Disconnect**. This calls Strava's deauthorize endpoint, sets `revoked_at`, and wipes the stored tokens. The page then shows "not connected", and you can connect again.

## Layout

```
app/core/      config, DB session, Fernet helpers, failed-auth rate limiter, deps
app/models/    SQLAlchemy models
app/services/  connections (upsert/revoke), tokens (transparent refresh), providers (provider-specific OAuth)
app/routers/   /auth/{provider}/connect|callback|disconnect, /api/connections
alembic/       migrations
static/        minimal test page
```

## Notes

- `provider` is stored as VARCHAR (not a native DB enum) so adding providers needs no `ALTER TYPE`. `trainingpeaks` is in the enum but has no OAuth; its auth routes return 404.
- One active connection per (user, provider) and per (provider, athlete) is enforced by partial unique indexes on `revoked_at IS NULL`.
- Failed callbacks (bad state, provider errors) are logged and counted per IP; 5 failures in 10 minutes returns 429. The counter is in-memory and per-process.
