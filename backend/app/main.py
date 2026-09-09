"""App factory. Run with: uv run uvicorn app.main:app --reload (from backend/)."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings as app_settings
from .errors import ApiError, api_error_handler
from .routers import auth as auth_router
from .routers import reviews as reviews_router
from .routers import settings as settings_router
from .services import ReplyGeneratorProtocol, get_reply_generator
from .store import DbStore


def _default_generator() -> ReplyGeneratorProtocol:
    # Real Groq pipeline only when GROQ_API_KEY is set; otherwise the
    # deterministic mock keeps tests offline and free (spec §7: no CI network).
    # Legacy OPENAI_API_KEY still opts into the OpenAI client explicitly.
    if os.getenv("GROQ_API_KEY"):
        return get_reply_generator()
    if os.getenv("OPENAI_API_KEY"):
        from .services import OpenAIReplyGenerator

        return OpenAIReplyGenerator()
    return get_reply_generator()


def create_app(store: DbStore | None = None, database_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Review-Reply Bot API",
        version="1.0.0",
        description=(
            "Single-user Reputation Manager backend (SQLAlchemy store, "
            "configured via DATABASE_URL). "
            "Implements openapi.yaml; no spec endpoint requires auth."
        ),
    )
    if store is None:
        store = DbStore(
            database_url=database_url or app_settings.database_url,
            seed=True,
            generator=_default_generator(),
        )
    app.state.store = store
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(reviews_router.router, prefix="/api")
    app.include_router(auth_router.router, prefix="/api")

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {"status": "ok", "docs": "/docs", "health": "/api/health"}

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
