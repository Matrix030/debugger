# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""HTML page routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def candidate_page(request: Request) -> HTMLResponse:
    """The single-page candidate workspace; question data loads via the API."""
    return templates.TemplateResponse(request, "candidate.html")
