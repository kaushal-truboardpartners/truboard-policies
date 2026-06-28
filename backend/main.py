"""FastAPI application entrypoint: app construction, lifespan, router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from storage.blob import BlobStorageService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate settings at startup — fails loudly if required env vars are missing.
    settings = get_settings()
    app.state.settings = settings
    # Process-wide Azure Blob client (async). Closed on shutdown.
    app.state.blob_service = BlobStorageService(settings)
    yield
    await app.state.blob_service.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TruBoard Policies API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ---- Routers (registered as each milestone lands) ----
    from admin.routes import router as admin_router
    from auth.routes import router as auth_router
    from documents.routes import router as documents_router

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(admin_router)
    # from chat.routes import router as chat_router
    # app.include_router(chat_router)

    return app


app = create_app()
