"""Integration tests for the sandbox executor (real subprocesses)."""

from pathlib import Path
import sys
import tempfile
import time

from runner_service.executor import check_syntax, run_batch, run_single_test
from runner_service.models import ExecuteRequest, TestSpec

CORRECT_CODE = "def add(a, b):\n    return a + b\n"


def make_request(code: str, tests: list[TestSpec], **kwargs) -> ExecuteRequest:
    return ExecuteRequest(
        code=code,
        function_name=kwargs.pop("function_name", "add"),
        tests=tests,
        time_limit_seconds=kwargs.pop("time_limit_seconds", 5),
        memory_limit_mb=kwargs.pop("memory_limit_mb", 256),
    )


def test_passing_and_failing_tests():
    response = run_batch(
        make_request(
            CORRECT_CODE,
            [
                TestSpec(name="ok", args=[1, 2], expected=3),
                TestSpec(name="wrong", args=[1, 2], expected=99),
            ],
        )
    )
    assert response.status == "ok"
    assert response.results[0].status == "passed"
    assert response.results[0].actual_repr == "3"
    assert response.results[1].status == "failed"
    assert response.results[1].actual_repr == "3"


def test_syntax_error_short_circuits():
    response = run_batch(
        make_request(
            "def add(a, b:\n    return a + b\n",
            [TestSpec(name="ok", args=[1, 2], expected=3)],
        )
    )
    assert response.status == "syntax_error"
    assert response.error is not None
    assert response.error.line == 1
    assert response.results == []


def test_check_syntax_reports_line():
    error = check_syntax("x = 1\ny = (\n")
    assert error is not None
    assert error.line in (2, 3)


def test_runtime_error_reports_candidate_frames():
    code = "def add(a, b):\n    return a + b + undefined_name\n"
    response = run_batch(
        make_request(code, [TestSpec(name="boom", args=[1, 2], expected=3)])
    )
    result = response.results[0]
    assert result.status == "error"
    assert "NameError" in (result.error_message or "")
    assert "line 2" in (result.error_message or "")
    assert "harness" not in (result.error_message or "")


def test_missing_function_reported():
    response = run_batch(
        make_request(
            "def other(): pass\n",
            [TestSpec(name="missing", args=[], expected=None)],
        )
    )
    result = response.results[0]
    assert result.status == "error"
    assert "not defined" in (result.error_message or "")


def test_crash_at_import_time_reported():
    response = run_batch(
        make_request(
            "raise RuntimeError('boom at import')\n\ndef add(a, b):\n    return a + b\n",
            [TestSpec(name="t", args=[1, 2], expected=3)],
        )
    )
    result = response.results[0]
    assert result.status == "error"
    assert "boom at import" in (result.error_message or "")


def test_infinite_loop_times_out_within_budget():
    code = "def add(a, b):\n    while True:\n        pass\n"
    start = time.monotonic()
    result = run_single_test(
        code,
        "add",
        TestSpec(name="loop", args=[1, 2], expected=3),
        time_limit_seconds=1,
        memory_limit_mb=256,
    )
    elapsed = time.monotonic() - start
    assert result.status == "timeout"
    assert "time limit" in (result.error_message or "")
    assert elapsed < 6


def test_tuple_normalizes_to_list():
    code = "def add(a, b):\n    return (a, b)\n"
    response = run_batch(
        make_request(code, [TestSpec(name="pair", args=[1, 2], expected=[1, 2])])
    )
    assert response.results[0].status == "passed"


def test_dict_and_nested_comparison():
    code = (
        "def add(a, b):\n"
        "    return {'sum': a + b, 'parts': [a, b], 'flags': {'ok': True}}\n"
    )
    expected = {"sum": 3, "parts": [1, 2], "flags": {"ok": True}}
    response = run_batch(
        make_request(code, [TestSpec(name="nested", args=[1, 2], expected=expected)])
    )
    assert response.results[0].status == "passed"


def test_non_serializable_return_is_clear_error():
    code = "def add(a, b):\n    return {1, 2}\n"
    response = run_batch(
        make_request(code, [TestSpec(name="set", args=[1, 2], expected=[1, 2])])
    )
    result = response.results[0]
    assert result.status == "error"
    assert "not JSON-comparable" in (result.error_message or "")


def test_stdout_captured_separately():
    code = 'def add(a, b):\n    print("debugging", a, b)\n    return a + b\n'
    response = run_batch(
        make_request(code, [TestSpec(name="prints", args=[1, 2], expected=3)])
    )
    result = response.results[0]
    assert result.status == "passed"
    assert "debugging 1 2" in result.stdout
    assert "DEBUGLAB_RESULT" not in result.stdout


def test_stdout_truncated():
    code = 'def add(a, b):\n    print("x" * 200_000)\n    return a + b\n'
    response = run_batch(
        make_request(code, [TestSpec(name="flood", args=[1, 2], expected=3)])
    )
    result = response.results[0]
    assert "[output truncated]" in result.stdout
    assert len(result.stdout) < 70_000


def test_workdir_cleaned_up():
    before = set(Path(tempfile.gettempdir()).glob("debuglab-*"))
    run_batch(
        make_request(CORRECT_CODE, [TestSpec(name="ok", args=[1, 2], expected=3)])
    )
    after = set(Path(tempfile.gettempdir()).glob("debuglab-*"))
    assert after <= before


def test_isolated_mode_blocks_site_packages():
    """-I mode: candidate code must not see the app's installed packages."""
    code = (
        "def add(a, b):\n"
        "    try:\n"
        "        import fastapi\n"
        "        return 'fastapi importable'\n"
        "    except ImportError:\n"
        "        return a + b\n"
    )
    response = run_batch(
        make_request(code, [TestSpec(name="no-site", args=[1, 2], expected=3)])
    )
    assert response.results[0].status == "passed"


def test_memory_limit_enforced():
    """A memory bomb must not pass; on Linux RLIMIT_AS kills it quickly."""
    if sys.platform == "darwin":
        import pytest

        pytest.skip("RLIMIT_AS is not reliably enforced on macOS")
    code = "def add(a, b):\n    data = ['x' * 1024] * (10**9)\n    return a + b\n"
    result = run_single_test(
        code,
        "add",
        TestSpec(name="bomb", args=[1, 2], expected=3),
        time_limit_seconds=5,
        memory_limit_mb=128,
    )
    assert result.status in ("error", "timeout")
