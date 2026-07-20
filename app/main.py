# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""DebugLab FastAPI app factory."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import candidate, pages
from app.paths import STATIC_DIR


def create_app() -> FastAPI:
    """Create and configure the DebugLab application."""
    app = FastAPI(
        title="DebugLab",
        description="Local Python debugging interview practice",
        version="1.0.0",
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(pages.router)
    app.include_router(candidate.router)
    return app


app = create_app()
