# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI app for the execution sandbox. Internal network only."""

from fastapi import FastAPI

from .executor import run_batch
from .models import ExecuteRequest, ExecuteResponse

app = FastAPI(title="DebugLab Runner", docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the compose healthcheck."""
    return {"status": "ok"}


@app.post("/run")
def run(request: ExecuteRequest) -> ExecuteResponse:
    """Execute a batch of tests against candidate code.

    Declared ``def`` (not ``async``) so FastAPI runs it in the threadpool;
    the subprocess work is blocking.
    """
    return run_batch(request)
