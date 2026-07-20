"""Shared fixtures for DebugLab tests."""

from pathlib import Path
import sys
import textwrap

from fastapi.testclient import TestClient
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNNER_DIR = PROJECT_ROOT / "runner"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from app.api import candidate  # noqa: E402
from app.execution import (  # noqa: E402
    RunnerResponse,
    RunnerSyntaxError,
    RunnerTestResult,
    get_execution_client,
)
from app.main import create_app  # noqa: E402
from app.questions import Question, QuestionBank, TestCase  # noqa: E402

HIDDEN_ARG_SENTINEL = 987654321987
HIDDEN_EXPECTED_SENTINEL = "SECRET-HIDDEN-EXPECTED-VALUE"
HIDDEN_NAME_SENTINEL = "secret hidden test name"
NOTES_SENTINEL = "SECRET-INTERVIEWER-NOTES"
SOLUTION_SENTINEL = "SECRET_SOLUTION_MARKER"


def question_dict(**overrides):
    """A valid question definition; override fields per test."""
    base = {
        "id": "sample-question",
        "title": "Sample Question",
        "difficulty": "easy",
        "tags": ["debugging", "sample"],
        "description": "Fix the bug.\n\n### Task\n\n- Make it work.",
        "constraints": ["1 <= n <= 10"],
        "function_name": "double_it",
        "language": "python",
        "starter_code": "def double_it(n):\n    return n + n + 1\n",
        "visible_tests": [
            {"name": "doubles two", "args": [2], "expected": 4},
            {"name": "doubles zero", "args": [0], "expected": 0},
        ],
        "hidden_tests": [
            {
                "name": HIDDEN_NAME_SENTINEL,
                "args": [HIDDEN_ARG_SENTINEL],
                "expected": HIDDEN_EXPECTED_SENTINEL,
            },
            {"name": "hidden negative", "args": [-3], "expected": -6},
            {"name": "hidden large", "args": [1000], "expected": 2000},
        ],
        "interviewer_notes": f"{NOTES_SENTINEL}: the +1 is the bug.",
        "solution": f"def double_it(n):\n    # {SOLUTION_SENTINEL}\n    return n * 2\n",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
    }
    base.update(overrides)
    return base


def write_question(directory: Path, filename: str, data: dict) -> Path:
    path = directory / filename
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def questions_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "questions"
    directory.mkdir()
    write_question(directory, "001_sample.yaml", question_dict())
    write_question(
        directory,
        "002_other.yaml",
        question_dict(
            id="other-question",
            title="Other Question",
            difficulty="medium",
        ),
    )
    return directory


class FakeExecutionClient:
    """Records execute() calls and returns a canned RunnerResponse."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.response: RunnerResponse | None = None
        self.raise_unavailable = False

    async def execute(
        self, question: Question, code: str, tests: list[TestCase]
    ) -> RunnerResponse:
        from app.execution import RunnerUnavailableError

        self.calls.append({"question_id": question.id, "code": code, "tests": tests})
        if self.raise_unavailable:
            raise RunnerUnavailableError("connection refused")
        if self.response is not None:
            return self.response
        return RunnerResponse(
            status="ok",
            results=[
                RunnerTestResult(
                    name=test.name,
                    status="passed",
                    actual_repr=repr(test.expected),
                )
                for test in tests
            ],
        )


@pytest.fixture
def fake_execution() -> FakeExecutionClient:
    return FakeExecutionClient()


@pytest.fixture
def client(questions_dir, fake_execution, monkeypatch) -> TestClient:
    monkeypatch.setattr(candidate, "question_bank", QuestionBank(questions_dir))
    app = create_app()
    app.dependency_overrides[get_execution_client] = lambda: fake_execution
    return TestClient(app)


def make_failed_response(tests: list[TestCase]) -> RunnerResponse:
    """A canned response where every test fails with detail-rich fields."""
    return RunnerResponse(
        status="ok",
        results=[
            RunnerTestResult(
                name=test.name,
                status="failed",
                actual_repr="'wrong-answer'",
                stdout=f"debug output for {test.name}",
                stderr=f"warning while running {test.name}",
                error_message=None,
            )
            for test in tests
        ],
    )


def make_syntax_error_response() -> RunnerResponse:
    return RunnerResponse(
        status="syntax_error",
        error=RunnerSyntaxError(message="invalid syntax: def broken(", line=1),
    )


def solution_code() -> str:
    return textwrap.dedent(
        """
        def double_it(n):
            return n * 2
        """
    )
