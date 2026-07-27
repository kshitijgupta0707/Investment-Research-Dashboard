"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.middleware.errors import register_exception_handlers
from app.middleware.logging import RequestContextMiddleware
from app.routes import auth as auth_routes
from app.routes import health as health_routes
from app.routes import queries as query_routes
from app.routes import reports as report_routes
from app.routes import research as research_routes
from app.routes import watchlist as watchlist_routes
from app.schemas.envelope import Envelope, ok
from app.utils.config import get_settings
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(
    title="Investment Research Dashboard API",
    description="Multi-tenant equity research API with LLM-driven tool orchestration.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Registered last, so it is the outermost layer: the request id exists before
# anything else runs, and every response leaves with the header attached.
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(research_routes.router)
app.include_router(report_routes.router)
app.include_router(watchlist_routes.router)
app.include_router(query_routes.router)


@app.get("/", response_model=Envelope[dict[str, str]])
async def root() -> Envelope[dict[str, str]]:
    return ok({"service": "investment-research-dashboard-api", "version": app.version})
