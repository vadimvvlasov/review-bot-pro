"""App factory. Run with: uv run uvicorn app.main:app --reload (from backend/)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .errors import ApiError, api_error_handler
from .routers import auth as auth_router
from .routers import reviews as reviews_router
from .routers import settings as settings_router
from .store import InMemoryStore


def create_app(store: InMemoryStore | None = None) -> FastAPI:
    app = FastAPI(
        title="Review-Reply Bot API",
        version="1.0.0",
        description=(
            "Single-user Reputation Manager backend (in-memory store). "
            "Implements openapi.yaml; no spec endpoint requires auth."
        ),
    )
    app.state.store = store if store is not None else InMemoryStore(seed=True)
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
