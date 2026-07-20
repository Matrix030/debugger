"""Every shipped question must be honest: solution passes, starter fails.

Runs the real sandbox executor over data/questions/*.yaml, proving that
the tests are solvable and that they actually catch the planted bugs.
"""

import pytest

from app.questions import Question, question_bank
from runner_service.executor import run_batch
from runner_service.models import ExecuteRequest, TestSpec

SEED_QUESTIONS = question_bank.all()


def to_specs(question: Question) -> list[TestSpec]:
    return [
        TestSpec(name=test.name, args=test.args, expected=test.expected)
        for test in question.visible_tests + question.hidden_tests
    ]


@pytest.mark.parametrize("question", SEED_QUESTIONS, ids=[q.id for q in SEED_QUESTIONS])
def test_solution_passes_all_tests(question):
    response = run_batch(
        ExecuteRequest(
            code=question.solution,
            function_name=question.function_name,
            tests=to_specs(question),
            time_limit_seconds=question.time_limit_seconds,
            memory_limit_mb=question.memory_limit_mb,
        )
    )
    assert response.status == "ok"
    failing = [r for r in response.results if r.status != "passed"]
    assert not failing, (
        f"solution for {question.id} fails: "
        f"{[(r.name, r.status, r.error_message) for r in failing]}"
    )


@pytest.mark.parametrize("question", SEED_QUESTIONS, ids=[q.id for q in SEED_QUESTIONS])
def test_starter_code_fails_at_least_one_test(question):
    response = run_batch(
        ExecuteRequest(
            code=question.starter_code,
            function_name=question.function_name,
            tests=to_specs(question),
            time_limit_seconds=question.time_limit_seconds,
            memory_limit_mb=question.memory_limit_mb,
        )
    )
    assert response.status == "ok", "starter code must at least compile"
    not_passing = [r for r in response.results if r.status != "passed"]
    assert not_passing, (
        f"starter code for {question.id} passes every test - "
        "the planted bug is not caught"
    )
