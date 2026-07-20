# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate-facing JSON API.

Every response goes through the models in :mod:`app.schemas`, which have no
fields for hidden tests, interviewer notes, or the reference solution — the
redaction is structural, not conventional.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
import markdown

from app.execution import (
    ExecutionClient,
    RunnerResponse,
    RunnerTestResult,
    RunnerUnavailableError,
    get_execution_client,
)
from app.questions import Question, TestCase, question_bank
from app.schemas import (
    CandidateQuestion,
    ExecuteRequest,
    HiddenTestResult,
    QuestionSummary,
    RunResponse,
    SubmitResponse,
    SyntaxErrorInfo,
    VisibleTest,
    VisibleTestResult,
)

router = APIRouter(prefix="/api", tags=["candidate"])

ExecutionClientDep = Annotated[ExecutionClient, Depends(get_execution_client)]

_RUNNER_DOWN_DETAIL = (
    "Code execution service is unavailable. "
    "Make sure the runner container is up (docker compose up)."
)


def _render_markdown(text: str) -> str:
    return markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])


def _get_question_or_404(question_id: str) -> Question:
    question = question_bank.get(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Unknown question id")
    return question


@router.get("/questions")
def list_questions() -> list[QuestionSummary]:
    """Navigation list: id, title, difficulty, tags, position."""
    questions = question_bank.all()
    total = len(questions)
    return [
        QuestionSummary(
            id=question.id,
            title=question.title,
            difficulty=question.difficulty,
            category=question.category,
            tags=question.tags,
            index=index,
            total=total,
        )
        for index, question in enumerate(questions)
    ]


@router.get("/questions/{question_id}")
def get_question(question_id: str) -> CandidateQuestion:
    """Candidate view of one question (never includes hidden data)."""
    question = _get_question_or_404(question_id)
    return CandidateQuestion(
        id=question.id,
        title=question.title,
        difficulty=question.difficulty,
        category=question.category,
        tags=question.tags,
        description_html=_render_markdown(question.description),
        constraints=question.constraints,
        function_name=question.function_name,
        language=question.language,
        starter_code=question.starter_code,
        visible_tests=[
            VisibleTest(name=test.name, args=test.args, expected=test.expected)
            for test in question.visible_tests
        ],
        time_limit_seconds=question.time_limit_seconds,
        memory_limit_mb=question.memory_limit_mb,
        index=question_bank.index_of(question.id),
        total=len(question_bank.all()),
    )


def _visible_result(
    question: Question, index: int, result: RunnerTestResult
) -> VisibleTestResult:
    expected = question.visible_tests[index].expected
    return VisibleTestResult(
        name=result.name,
        status=result.status,
        expected=expected,
        actual=result.actual_repr,
        error=result.error_message,
        stdout=result.stdout,
        stderr=result.stderr,
    )


async def _execute_or_503(
    client: ExecutionClient, question: Question, code: str, tests: list[TestCase]
) -> RunnerResponse:
    try:
        return await client.execute(question, code, tests)
    except RunnerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_RUNNER_DOWN_DETAIL) from exc


@router.post("/run")
async def run_code(request: ExecuteRequest, client: ExecutionClientDep) -> RunResponse:
    """Run Code: executes visible tests only."""
    question = _get_question_or_404(request.question_id)
    outcome = await _execute_or_503(
        client, question, request.code, question.visible_tests
    )
    if outcome.status == "syntax_error":
        return RunResponse(
            question_id=question.id,
            status="syntax_error",
            syntax_error=_syntax_error(outcome),
        )
    visible = [
        _visible_result(question, index, result)
        for index, result in enumerate(outcome.results)
    ]
    passed = sum(1 for result in visible if result.status == "passed")
    return RunResponse(
        question_id=question.id,
        status="ok",
        visible_results=visible,
        passed_count=passed,
        total_count=len(visible),
        all_passed=passed == len(visible) and len(visible) > 0,
    )


@router.post("/submit")
async def submit_code(
    request: ExecuteRequest, client: ExecutionClientDep
) -> SubmitResponse:
    """Submit: executes visible + hidden tests; hidden detail is redacted."""
    question = _get_question_or_404(request.question_id)
    all_tests = question.visible_tests + question.hidden_tests
    outcome = await _execute_or_503(client, question, request.code, all_tests)
    if outcome.status == "syntax_error":
        return SubmitResponse(
            question_id=question.id,
            status="syntax_error",
            syntax_error=_syntax_error(outcome),
        )
    visible_count = len(question.visible_tests)
    visible = [
        _visible_result(question, index, result)
        for index, result in enumerate(outcome.results[:visible_count])
    ]
    hidden = [
        HiddenTestResult(label=f"Hidden test {number}", status=result.status)
        for number, result in enumerate(outcome.results[visible_count:], start=1)
    ]
    visible_passed = sum(1 for result in visible if result.status == "passed")
    hidden_passed = sum(1 for result in hidden if result.status == "passed")
    total = len(visible) + len(hidden)
    passed = visible_passed + hidden_passed
    return SubmitResponse(
        question_id=question.id,
        status="ok",
        visible_results=visible,
        hidden_results=hidden,
        passed_count=passed,
        total_count=total,
        hidden_passed_count=hidden_passed,
        hidden_total_count=len(hidden),
        all_passed=passed == total and total > 0,
    )


def _syntax_error(outcome: RunnerResponse) -> SyntaxErrorInfo:
    if outcome.error is None:
        return SyntaxErrorInfo(message="Syntax error", line=None)
    return SyntaxErrorInfo(message=outcome.error.message, line=outcome.error.line)
