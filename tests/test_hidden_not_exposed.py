"""Hidden tests, interviewer notes, and solutions must never reach the browser.

Every candidate-facing endpoint's raw response body is scanned for sentinel
values that only exist in hidden/interviewer fields of the fixture question.
"""

from tests.conftest import (
    HIDDEN_ARG_SENTINEL,
    HIDDEN_EXPECTED_SENTINEL,
    HIDDEN_NAME_SENTINEL,
    NOTES_SENTINEL,
    SOLUTION_SENTINEL,
    make_failed_response,
)

FORBIDDEN = [
    str(HIDDEN_ARG_SENTINEL),
    HIDDEN_EXPECTED_SENTINEL,
    HIDDEN_NAME_SENTINEL,
    NOTES_SENTINEL,
    SOLUTION_SENTINEL,
    "interviewer_notes",
    "hidden_tests",
]


def assert_clean(body: str, context: str) -> None:
    for needle in FORBIDDEN:
        assert needle not in body, f"{context} leaked {needle!r}"


def test_question_list_is_clean(client):
    response = client.get("/api/questions")
    assert response.status_code == 200
    assert_clean(response.text, "GET /api/questions")


def test_question_detail_is_clean(client):
    response = client.get("/api/questions/sample-question")
    assert response.status_code == 200
    assert_clean(response.text, "GET /api/questions/sample-question")


def test_run_response_is_clean(client):
    response = client.post(
        "/api/run",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    )
    assert response.status_code == 200
    assert_clean(response.text, "POST /api/run")


def test_submit_response_is_clean_on_pass(client):
    response = client.post(
        "/api/submit",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    )
    assert response.status_code == 200
    assert_clean(response.text, "POST /api/submit (pass)")


def test_submit_response_is_clean_on_failure(client, fake_execution, questions_dir):
    """Even failing hidden tests must not leak names, stdout, stderr, or values.

    The fake runner echoes detail-rich results (including the hidden test's
    real name in stdout/stderr); the API must redact everything but a generic
    label and status.
    """
    from app.questions import QuestionBank

    bank = QuestionBank(questions_dir)
    question = bank.get("sample-question")
    all_tests = question.visible_tests + question.hidden_tests
    fake_execution.response = make_failed_response(all_tests)
    response = client.post(
        "/api/submit",
        json={"question_id": "sample-question", "code": "def double_it(n): ..."},
    )
    assert response.status_code == 200
    assert_clean(response.text, "POST /api/submit (failures)")
    data = response.json()
    for hidden in data["hidden_results"]:
        assert set(hidden.keys()) == {"label", "status"}


def test_candidate_page_is_clean(client):
    response = client.get("/")
    assert_clean(response.text, "GET /")


def test_no_interviewer_or_ai_routes(client):
    """Routes from the old AI platform must be gone."""
    for path in ("/setup", "/config", "/interviewer", "/known-questions/manage"):
        assert client.get(path).status_code == 404, path
