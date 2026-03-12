"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from visa_disputes_agent.api.routes import router, set_brain
from visa_disputes_agent.config.settings import get_settings
from visa_disputes_agent.orchestrator.brain import DisputeBrain

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler - initializes and cleans up the brain."""
    settings = get_settings()
    brain = DisputeBrain(settings=settings)
    set_brain(brain)
    logger.info("brain_ready", version=settings.app_version)
    yield
    await brain.stop()
    logger.info("brain_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Autonomous AI agent system for processing Visa disputes "
            "according to Visa Core Rules. Replaces human dispute processors "
            "by picking tasks from a queue and executing them using encoded "
            "Visa dispute processing rules."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    return app


# Application instance for uvicorn
app = create_app()
