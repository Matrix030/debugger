# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Sandboxed execution of candidate code, one subprocess per test case.

Isolation layers (in addition to the hardened container this service runs
in — non-root, read-only rootfs, no-network, pids/memory limits):

* ``python -I -S`` — isolated mode, no site packages, no env injection.
* A fresh throwaway working directory per test, deleted afterwards.
* POSIX rlimits (CPU, address space, processes, file size, open files)
  applied between ``fork`` and ``exec``; each is best-effort so the same
  code also runs during host-side tests on macOS.
* A wall-clock timeout enforced with ``SIGKILL`` on the whole process group.
"""

from collections.abc import Callable
import contextlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile

from .harness import HARNESS_SOURCE, SENTINEL
from .models import (
    ExecuteRequest,
    ExecuteResponse,
    SyntaxErrorInfo,
    TestResult,
    TestSpec,
)

_OUTPUT_LIMIT_BYTES = 64 * 1024
_MIN_MEMORY_MB = 128


def _output_cap(text: str) -> str:
    if len(text) <= _OUTPUT_LIMIT_BYTES:
        return text
    return text[:_OUTPUT_LIMIT_BYTES] + "\n... [output truncated]"


def _make_preexec(time_limit_seconds: int, memory_limit_mb: int) -> Callable[[], None]:
    memory_bytes = max(memory_limit_mb, _MIN_MEMORY_MB) * 1024 * 1024

    def _apply_limits() -> None:
        limits = [
            (resource.RLIMIT_CPU, (time_limit_seconds, time_limit_seconds + 1)),
            (resource.RLIMIT_AS, (memory_bytes, memory_bytes)),
            (resource.RLIMIT_NPROC, (16, 16)),
            (resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024)),
            (resource.RLIMIT_NOFILE, (64, 64)),
        ]
        for limit, value in limits:
            # Best-effort: some limits are unavailable or already lower
            # (notably on macOS during host-side test runs).
            with contextlib.suppress(ValueError, OSError):
                resource.setrlimit(limit, value)

    return _apply_limits


def check_syntax(code: str) -> SyntaxErrorInfo | None:
    """Compile the code without executing it; return error details if invalid."""
    try:
        compile(code, "candidate.py", "exec")
    except SyntaxError as exc:
        message = exc.msg or "invalid syntax"
        if exc.text and exc.text.strip():
            message = f"{message}: {exc.text.strip()}"
        return SyntaxErrorInfo(message=message, line=exc.lineno)
    except ValueError as exc:  # e.g. source containing null bytes
        return SyntaxErrorInfo(message=str(exc), line=None)
    return None


def run_single_test(
    code: str,
    function_name: str,
    test: TestSpec,
    time_limit_seconds: int,
    memory_limit_mb: int,
) -> TestResult:
    """Execute one test case in an isolated subprocess."""
    workdir = tempfile.mkdtemp(prefix="debuglab-")
    try:
        _write(workdir, "candidate.py", code)
        _write(workdir, "harness.py", HARNESS_SOURCE)
        _write(
            workdir,
            "test.json",
            json.dumps(
                {
                    "function_name": function_name,
                    "args": test.args,
                    "expected": test.expected,
                }
            ),
        )

        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-I", "-S", "harness.py"],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
            env={"PATH": "/usr/bin:/bin"},
            preexec_fn=_make_preexec(time_limit_seconds, memory_limit_mb),
        )
        try:
            stdout, stderr = process.communicate(timeout=time_limit_seconds + 1)
        except subprocess.TimeoutExpired:
            _kill_group(process)
            stdout, stderr = process.communicate()
            return TestResult(
                name=test.name,
                status="timeout",
                stdout=_output_cap(stdout or ""),
                stderr=_output_cap(stderr or ""),
                error_message=(
                    f"execution exceeded the {time_limit_seconds}s time limit"
                ),
            )
        return _parse_result(test, process.returncode, stdout or "", stderr or "")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_batch(request: ExecuteRequest) -> ExecuteResponse:
    """Syntax-check the code, then run every test in its own subprocess."""
    syntax_error = check_syntax(request.code)
    if syntax_error is not None:
        return ExecuteResponse(status="syntax_error", error=syntax_error)

    results = [
        run_single_test(
            request.code,
            request.function_name,
            test,
            request.time_limit_seconds,
            request.memory_limit_mb,
        )
        for test in request.tests
    ]
    return ExecuteResponse(status="ok", results=results)


def _write(directory: str, filename: str, content: str) -> None:
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as handle:
        handle.write(content)


def _kill_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        process.kill()


def _parse_result(
    test: TestSpec, returncode: int | None, stdout: str, stderr: str
) -> TestResult:
    user_stdout_lines: list[str] = []
    payload: dict[str, object] | None = None
    for line in stdout.splitlines():
        if line.startswith(SENTINEL):
            try:
                parsed = json.loads(line[len(SENTINEL) :])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                payload = parsed
        else:
            user_stdout_lines.append(line)
    user_stdout = "\n".join(user_stdout_lines)

    if payload is None:
        return TestResult(
            name=test.name,
            status="error",
            stdout=_output_cap(user_stdout),
            stderr=_output_cap(stderr),
            error_message=(
                f"process exited unexpectedly (exit code {returncode}); "
                "this usually means the memory limit was exceeded or the "
                "process was killed"
            ),
        )

    status_value = payload.get("status")
    status: str = status_value if isinstance(status_value, str) else "error"
    if status not in ("passed", "failed", "error"):
        status = "error"
    actual_repr = payload.get("actual_repr")
    error_message = payload.get("error_message")
    return TestResult(
        name=test.name,
        status=status,  # type: ignore[arg-type]
        actual_repr=actual_repr if isinstance(actual_repr, str) else None,
        stdout=_output_cap(user_stdout),
        stderr=_output_cap(stderr),
        error_message=error_message if isinstance(error_message, str) else None,
    )
