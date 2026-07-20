"""Run and Submit flows against a fake execution client."""

import httpx
import pytest

from app.execution import ExecutionClient, RunnerUnavailableError
from app.questions import QuestionBank
from tests.conftest import make_failed_response, make_syntax_error_response


def test_run_sends_only_visible_tests(client, fake_execution):
    response = client.post(
        "/api/run",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    )
    assert response.status_code == 200
    assert len(fake_execution.calls) == 1
    sent_tests = fake_execution.calls[0]["tests"]
    assert [test.name for test in sent_tests] == ["doubles two", "doubles zero"]


def test_run_all_passed(client):
    response = client.post(
        "/api/run",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    )
    data = response.json()
    assert data["status"] == "ok"
    assert data["all_passed"] is True
    assert data["passed_count"] == 2
    assert data["total_count"] == 2
    assert [r["status"] for r in data["visible_results"]] == ["passed", "passed"]


def test_run_reports_failures_with_detail(client, fake_execution, questions_dir):
    bank = QuestionBank(questions_dir)
    question = bank.get("sample-question")
    fake_execution.response = make_failed_response(question.visible_tests)
    data = client.post(
        "/api/run",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    ).json()
    assert data["all_passed"] is False
    assert data["passed_count"] == 0
    first = data["visible_results"][0]
    assert first["status"] == "failed"
    assert first["expected"] == 4
    assert first["actual"] == "'wrong-answer'"
    assert "debug output" in first["stdout"]


def test_run_syntax_error(client, fake_execution):
    fake_execution.response = make_syntax_error_response()
    data = client.post(
        "/api/run",
        json={"question_id": "sample-question", "code": "def broken("},
    ).json()
    assert data["status"] == "syntax_error"
    assert data["syntax_error"]["line"] == 1
    assert "invalid syntax" in data["syntax_error"]["message"]
    assert data["visible_results"] == []
    assert data["all_passed"] is False


def test_submit_sends_visible_plus_hidden(client, fake_execution):
    response = client.post(
        "/api/submit",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    )
    assert response.status_code == 200
    sent_tests = fake_execution.calls[0]["tests"]
    assert len(sent_tests) == 5  # 2 visible + 3 hidden


def test_submit_success_shape(client):
    data = client.post(
        "/api/submit",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    ).json()
    assert data["all_passed"] is True
    assert data["passed_count"] == 5
    assert data["total_count"] == 5
    assert data["hidden_passed_count"] == 3
    assert data["hidden_total_count"] == 3
    assert len(data["visible_results"]) == 2
    assert [r["label"] for r in data["hidden_results"]] == [
        "Hidden test 1",
        "Hidden test 2",
        "Hidden test 3",
    ]


def test_submit_partial_failure(client, fake_execution, questions_dir):
    bank = QuestionBank(questions_dir)
    question = bank.get("sample-question")
    all_tests = question.visible_tests + question.hidden_tests
    fake_execution.response = make_failed_response(all_tests)
    data = client.post(
        "/api/submit",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    ).json()
    assert data["all_passed"] is False
    assert data["passed_count"] == 0
    assert all(r["status"] == "failed" for r in data["hidden_results"])


def test_runner_unavailable_returns_503(client, fake_execution):
    fake_execution.raise_unavailable = True
    for endpoint in ("/api/run", "/api/submit"):
        response = client.post(
            endpoint,
            json={"question_id": "sample-question", "code": "x = 1"},
        )
        assert response.status_code == 503
        assert "execution service" in response.json()["detail"].lower()


async def test_execution_client_payload_and_parsing(questions_dir):
    """ExecutionClient sends the runner contract and parses the response."""
    bank = QuestionBank(questions_dir)
    question = bank.get("sample-question")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "error": None,
                "results": [
                    {
                        "name": "doubles two",
                        "status": "passed",
                        "actual_repr": "4",
                        "stdout": "",
                        "stderr": "",
                        "error_message": None,
                    }
                ],
            },
        )

    client = ExecutionClient(
        base_url="http://runner.test", transport=httpx.MockTransport(handler)
    )
    result = await client.execute(
        question, "def double_it(n): return n * 2", question.visible_tests[:1]
    )
    assert captured["url"] == "http://runner.test/run"
    assert captured["payload"]["function_name"] == "double_it"
    assert captured["payload"]["time_limit_seconds"] == 5
    assert captured["payload"]["memory_limit_mb"] == 256
    assert captured["payload"]["tests"] == [
        {"name": "doubles two", "args": [2], "expected": 4}
    ]
    assert result.status == "ok"
    assert result.results[0].status == "passed"


async def test_execution_client_unreachable(questions_dir):
    bank = QuestionBank(questions_dir)
    question = bank.get("sample-question")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = ExecutionClient(
        base_url="http://runner.test", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RunnerUnavailableError):
        await client.execute(question, "x = 1", question.visible_tests)
