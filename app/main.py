from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI

from app.config import settings
from app.database import create_tables, engine
from app.routers import approvals, dashboard, webhooks

import app.models  # noqa: F401 — ensures all models register with Base.metadata


def configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog()
    await create_tables()
    logger.info("startup", environment=settings.environment)
    yield
    await engine.dispose()
    logger.info("shutdown")


app = FastAPI(
    title="AI Documentation Agent",
    description="Watches GitHub PRs, detects stale docs, generates surgical edits for human approval.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhooks.router)
app.include_router(approvals.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
