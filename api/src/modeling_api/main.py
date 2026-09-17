"""Modeling Copilot API application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from modeling_api.core.auth import get_user
from modeling_api.core.config import settings
from modeling_api.core.errors import ErrorResponse, register_error_handlers
from modeling_api.db.client import client, create_indexes, db
from modeling_api.db.initial_data import seed_initial_data
from modeling_api.routes import auth, feedback, languages, models, server_time, tasks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await create_indexes()
    await seed_initial_data()
    yield
    await client.close()


app = FastAPI(
    title="Modeling Copilot API",
    description=(
        "Versioned storage for modeling languages, tasks, models, task edits, "
        "sample solutions, and feedback. All domain endpoints require JWT authentication."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    redoc_url=None,
)

register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Location"],
)

# Public token-inspection route without the /v1 authentication dependency.
app.include_router(auth.router)

# All domain routes use the /v1 prefix and require JWT authentication.
api = APIRouter(
    prefix="/v1",
    dependencies=[Depends(get_user)],
    responses={
        code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 422, 503)
    },
)
api.include_router(languages.router)
api.include_router(tasks.router)
api.include_router(models.router)
api.include_router(feedback.router)
api.include_router(server_time.router)
app.include_router(api)


@app.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def ready() -> dict[str, str]:
    await db.command("ping")
    return {"status": "ok"}
