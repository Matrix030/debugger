# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Wire contract between the web app and the execution sandbox."""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field


class TestSpec(BaseModel):
    """One test to execute: call the function with args, compare to expected."""

    __test__: ClassVar[bool] = False  # not a pytest class despite the name

    name: str
    args: list[Any]
    expected: Any = None


class ExecuteRequest(BaseModel):
    """A batch of tests to run against one piece of candidate code."""

    code: str = Field(max_length=200_000)
    function_name: str
    tests: list[TestSpec]
    time_limit_seconds: int = Field(default=5, ge=1, le=30)
    memory_limit_mb: int = Field(default=256, ge=64, le=1024)


class SyntaxErrorInfo(BaseModel):
    """Syntax error details reported before any test executes."""

    message: str
    line: int | None = None


class TestResult(BaseModel):
    """Outcome of a single test case."""

    __test__: ClassVar[bool] = False  # not a pytest class despite the name

    name: str
    status: Literal["passed", "failed", "error", "timeout"]
    actual_repr: str | None = None
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None


class ExecuteResponse(BaseModel):
    """Overall outcome for a batch."""

    status: Literal["ok", "syntax_error"]
    error: SyntaxErrorInfo | None = None
    results: list[TestResult] = Field(default_factory=list)
