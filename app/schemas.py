# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate-facing API schemas.

These response models are the privacy boundary: they structurally have no
fields for hidden test inputs/outputs, interviewer notes, or the reference
solution, so those can never be serialized to the browser.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

TestStatus = Literal["passed", "failed", "error", "timeout"]


class QuestionSummary(BaseModel):
    """Entry in the question navigation list."""

    id: str
    title: str
    difficulty: str
    category: str
    tags: list[str]
    index: int
    total: int


class VisibleTest(BaseModel):
    """A visible test case as shown to the candidate."""

    name: str
    args: list[Any]
    expected: Any = None


class CandidateQuestion(BaseModel):
    """Full candidate view of one question. No hidden data by construction."""

    id: str
    title: str
    difficulty: str
    category: str
    tags: list[str]
    description_html: str
    constraints: list[str]
    function_name: str
    language: str
    starter_code: str
    visible_tests: list[VisibleTest]
    time_limit_seconds: int
    memory_limit_mb: int
    index: int
    total: int


class ExecuteRequest(BaseModel):
    """Body for both ``/api/run`` and ``/api/submit``."""

    question_id: str
    code: str = Field(max_length=100_000)


class SyntaxErrorInfo(BaseModel):
    """Details of a syntax error in submitted code."""

    message: str
    line: int | None = None


class VisibleTestResult(BaseModel):
    """Full result detail for a visible test."""

    name: str
    status: TestStatus
    expected: Any = None
    actual: Any = None
    error: str | None = None
    stdout: str = ""
    stderr: str = ""


class HiddenTestResult(BaseModel):
    """Redacted result for a hidden test: label and status only."""

    label: str
    status: TestStatus


class RunResponse(BaseModel):
    """Result of Run Code (visible tests only)."""

    question_id: str
    status: Literal["ok", "syntax_error"]
    syntax_error: SyntaxErrorInfo | None = None
    visible_results: list[VisibleTestResult] = Field(default_factory=list)
    passed_count: int = 0
    total_count: int = 0
    all_passed: bool = False


class SubmitResponse(RunResponse):
    """Result of Submit (visible + hidden tests, hidden detail redacted)."""

    hidden_results: list[HiddenTestResult] = Field(default_factory=list)
    hidden_passed_count: int = 0
    hidden_total_count: int = 0
