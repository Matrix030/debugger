# Copyright 2026 DebugLab Contributors
# SPDX-License-Identifier: Apache-2.0
"""Static harness script executed inside the sandbox subprocess.

The harness runs in a throwaway working directory containing:

* ``candidate.py`` — the submitted code, verbatim.
* ``test.json`` — ``{"function_name": ..., "args": [...], "expected": ...}``.

It executes the candidate module, calls the target function with the test
arguments, normalizes the return value through a JSON round-trip (so tuples
compare equal to lists and YAML-authored expectations match), and prints a
single machine-readable result line prefixed with :data:`SENTINEL` as its
final output. Anything the candidate prints lands on stdout *before* the
sentinel and is captured separately by the executor.
"""

SENTINEL = "DEBUGLAB_RESULT:"

HARNESS_SOURCE = """
import json
import sys
import traceback

SENTINEL = "DEBUGLAB_RESULT:"


def _emit(payload):
    sys.stdout.flush()
    sys.stderr.flush()
    print(SENTINEL + json.dumps(payload))
    sys.stdout.flush()


def _candidate_traceback(exc):
    frames = traceback.extract_tb(exc.__traceback__)
    lines = []
    for frame in frames:
        if frame.filename.endswith("candidate.py"):
            location = "line " + str(frame.lineno)
            if frame.name and frame.name != "<module>":
                location += " in " + frame.name
            lines.append(location + ": " + (frame.line or "").strip())
    summary = type(exc).__name__
    message = str(exc)
    if message:
        summary += ": " + message
    if lines:
        return summary + "\\n" + "\\n".join(lines)
    return summary


def main():
    with open("test.json", encoding="utf-8") as handle:
        spec = json.load(handle)

    with open("candidate.py", encoding="utf-8") as handle:
        source = handle.read()

    namespace = {"__name__": "candidate", "__file__": "candidate.py"}
    try:
        exec(compile(source, "candidate.py", "exec"), namespace)
    except BaseException as exc:  # noqa: B036 - report anything the code raises
        _emit({"status": "error",
               "error_message": "code failed while loading: "
               + _candidate_traceback(exc)})
        return

    function = namespace.get(spec["function_name"])
    if not callable(function):
        _emit({"status": "error",
               "error_message": "function " + repr(spec["function_name"])
               + " is not defined"})
        return

    try:
        actual = function(*spec["args"])
    except BaseException as exc:  # noqa: B036
        _emit({"status": "error", "error_message": _candidate_traceback(exc)})
        return

    try:
        normalized = json.loads(json.dumps(actual))
    except (TypeError, ValueError):
        _emit({"status": "error",
               "actual_repr": repr(actual)[:1000],
               "error_message": "return value of type "
               + type(actual).__name__
               + " is not JSON-comparable (return lists/dicts/strings/numbers/bools)"})
        return

    status = "passed" if normalized == spec["expected"] else "failed"
    _emit({"status": status, "actual_repr": repr(actual)[:1000]})


main()
"""
