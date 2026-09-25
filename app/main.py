import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.routers import api, auth
from app.services import providers

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    providers.register_providers()

    app = FastAPI(title="ClermontCyclistCoach")
    # Holds the OAuth state (CSRF) and the test-user id. Lax so the provider's redirect back carries it.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=settings.base_url.startswith("https"),
        max_age=60 * 60 * 24,
    )
    app.include_router(auth.router)
    app.include_router(api.router)

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
