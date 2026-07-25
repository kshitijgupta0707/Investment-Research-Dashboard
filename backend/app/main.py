"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Investment Research Dashboard API",
    description="Multi-tenant equity research API with LLM-driven tool orchestration.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "investment-research-dashboard-api", "version": app.version}
