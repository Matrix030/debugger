# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""HTTP client for the execution sandbox (the ``runner`` container).

Candidate code is never executed inside this web application process; it is
shipped to the runner service, which is isolated on an internal-only Docker
network with no internet egress.
"""

import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.questions import Question, TestCase

_DEFAULT_RUNNER_URL = "http://localhost:8001"


class RunnerUnavailableError(Exception):
    """Raised when the runner service cannot be reached."""


class RunnerSyntaxError(BaseModel):
    """Syntax error reported by the runner."""

    message: str
    line: int | None = None


class RunnerTestResult(BaseModel):
    """Per-test outcome reported by the runner."""

    name: str
    status: Literal["passed", "failed", "error", "timeout"]
    actual_repr: str | None = None
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None


class RunnerResponse(BaseModel):
    """Overall runner outcome for one batch of tests."""

    status: Literal["ok", "syntax_error"]
    error: RunnerSyntaxError | None = None
    results: list[RunnerTestResult] = Field(default_factory=list)


class ExecutionClient:
    """Thin async client for the runner's ``POST /run`` endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get("RUNNER_URL", _DEFAULT_RUNNER_URL)
        self._transport = transport

    async def execute(
        self, question: Question, code: str, tests: list[TestCase]
    ) -> RunnerResponse:
        """Run ``tests`` against ``code`` in the sandbox."""
        payload: dict[str, Any] = {
            "code": code,
            "function_name": question.function_name,
            "tests": [test.model_dump() for test in tests],
            "time_limit_seconds": question.time_limit_seconds,
            "memory_limit_mb": question.memory_limit_mb,
        }
        # Generous wall-clock budget: per-test limit plus scheduling overhead.
        timeout = 10.0 + len(tests) * (question.time_limit_seconds + 2)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                transport=self._transport,
                timeout=timeout,
            ) as client:
                response = await client.post("/run", json=payload)
        except httpx.HTTPError as exc:
            raise RunnerUnavailableError(str(exc)) from exc
        if response.status_code != 200:
            raise RunnerUnavailableError(f"runner returned HTTP {response.status_code}")
        return RunnerResponse.model_validate(response.json())


execution_client = ExecutionClient()


def get_execution_client() -> ExecutionClient:
    """FastAPI dependency; overridden in tests."""
    return execution_client
