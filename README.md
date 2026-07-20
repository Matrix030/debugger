# DebugLab

A locally hosted, HackerRank-style practice platform for **Python debugging interviews**.
Each question ships intentionally buggy code; the candidate edits it in a Monaco editor
until the tests pass. Everything runs on your machine — no accounts, no API keys, no
cloud services, no AI.

Built on the GrillKit codebase (FastAPI + Jinja2 + vanilla JS), with the AI interview
features removed and code execution moved into a hardened local sandbox container.

## What you get

- Split-pane interview UI: problem description left, Python editor right — both panes and the results console are drag-resizable (double-click a divider to reset)
- **Run Code** — executes the visible (sample) tests only
- **Submit** — executes visible **and** hidden tests; hidden results show only pass/fail
- **Reset Code** — restores the original buggy starter code
- Per-test results: pass/fail pills, expected vs. got, stdout/stderr, tracebacks
- Prev/Next navigation with `Question 2 of 6` progress, difficulty badge, tags
- Interview countdown timer (default 90:00) with Start/Pause/Reset, persisted across refreshes; expiry shows a clear state but never touches your code
- Candidate code auto-saved to the browser's localStorage per question — survives refreshes
- Questions are plain YAML files — add new ones without touching application code

## Architecture

Two Docker services:

```
┌────────────────────────┐         ┌─────────────────────────────┐
│  app  (port 8000)      │  HTTP   │  runner  (sandbox)          │
│  FastAPI + Jinja2      ├────────►│  FastAPI, POST /run         │
│  question bank (YAML)  │         │  subprocess per test case   │
│  run/submit API        │         │  python -I -S + rlimits     │
└────────────────────────┘         └─────────────────────────────┘
        │                                    ▲
   browser: Monaco editor,          internal-only Docker network
   localStorage persistence         (no internet, no host access)
```

- **Candidate code never executes in the web server process.** The app POSTs the code
  plus test cases to the `runner` service.
- The runner container is hardened: non-root user, read-only root filesystem, all
  Linux capabilities dropped, `no-new-privileges`, pids limit, 512 MB memory cap,
  1 CPU, and it sits on an **internal-only** Docker network — code you execute cannot
  reach the internet or the host.
- Each test case runs in its own subprocess (`python -I -S`: isolated mode, no site
  packages) inside a throwaway temp directory that is deleted after the run, with
  POSIX rlimits for CPU time, memory, process count, file size, and open files, plus
  a wall-clock timeout that SIGKILLs the whole process group.
- No database. Question files are read from `data/questions/` (bind-mounted, so edits
  appear on refresh); candidate code and the timer live in browser localStorage.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose v2

That's it. No API keys, no cloud accounts, no external databases.

## Quick start

```bash
cd grillkit
docker compose up --build
```

Then open **http://localhost:8000** — the first question loads automatically.

To stop: `Ctrl-C`, or `docker compose down` from another terminal.

To reset completely (containers + images):

```bash
docker compose down --rmi local
```

Candidate progress (saved code, timer) lives in the *browser*, not the server — clear
it from your browser's site data, or use the Reset Code button per question.

## Running without Docker (development)

```bash
uv sync --extra dev
uv run uvicorn runner_service.main:app --port 8001 --app-dir runner &  # sandbox-lite
uv run uvicorn app.main:app --port 8000
```

Note: outside Docker the runner still uses subprocess isolation and rlimits, but you
lose the container hardening and network isolation — use Docker for real sessions.

## Questions

Questions live in `data/questions/*.yaml`, loaded in filename order (use numeric
prefixes: `001_...`, `002_...`). `example.yaml` is a fully commented template that the
loader deliberately skips — copy it to start a new question:

```bash
cp data/questions/example.yaml data/questions/007_my_question.yaml
# edit it, then refresh the browser (no restart needed)
```

### Question schema

```yaml
id: validate-fragment-offsets   # unique lowercase-kebab slug
title: Validate Fragment Offsets Sequence
difficulty: medium              # easy | medium | hard
tags: [off-by-one, validation]  # short lowercase tags

description: |                  # Markdown; shown to the candidate
  Scenario paragraph...

  ### Task
  - Fix the implementation...

constraints:                    # list of strings, rendered as a section
  - "0 <= len(offsets) <= 10^5"

function_name: validate_fragments   # must be a top-level def in starter_code AND solution
language: python                    # only python is supported

starter_code: |                 # the intentionally buggy code the candidate sees
  def validate_fragments(offsets, max_offset, overlap_limit):
      ...

visible_tests:                  # shown to the candidate; Run executes these
  - name: rejects offset above mtu
    args: [[0, 800, 1600], 1400, 1]   # positional arguments (JSON values)
    expected: false                   # expected return value (JSON value)

hidden_tests:                   # never sent to the browser; Submit adds these
  - name: handles empty input
    args: [[], 1400, 1]
    expected: true

interviewer_notes: |            # for the question author; never exposed via the API
  Bug 1: ... Bug 2: ...

solution: |                     # reference fix; never exposed via the API
  def validate_fragments(offsets, max_offset, overlap_limit):
      ...

time_limit_seconds: 5           # per test case, 1-30 (default 5)
memory_limit_mb: 256            # 64-1024 (default 256)
```

Validation happens at load time: bad YAML, missing fields, duplicate ids, or a
`function_name` that isn't defined in both `starter_code` and `solution` produce a
clear error. The test suite additionally proves every shipped question's `solution`
passes **all** tests and its `starter_code` fails at least one.

### How test comparison works

Each test calls `function_name(*args)` and compares the return value with `expected`
after a JSON round-trip. Practical consequences:

- Returning a tuple compares equal to a YAML list (`(1, 2)` matches `[1, 2]`).
- Return values must be JSON-representable (numbers, strings, bools, None,
  lists, dicts). Sets or custom objects produce a clear "not JSON-comparable" error.
- Floats are compared exactly — design questions around integers/strings/bools.
- `print()` output is captured and shown to the candidate but never compared.

### Visible vs. hidden tests

- **Run Code** sends only `visible_tests` to the sandbox; results include full detail
  (expected, actual, stdout, stderr, tracebacks).
- **Submit** sends `visible_tests + hidden_tests`. Hidden results are redacted to a
  generic label (`Hidden test 1`) and a status — no inputs, expected values, output,
  or error text ever leave the server. `interviewer_notes` and `solution` are never
  serialized by any endpoint; the response models have no fields for them, and the
  test suite scans every candidate endpoint for leaks.

## The timer

- Lives in the top bar; default 90 minutes. Start/Pause/Reset controls.
- Persisted in localStorage — refreshing the page keeps the countdown.
- Under 5 minutes it turns amber; at zero it shows a red "Time expired" state.
- Expiry never auto-submits and never deletes code.

## Project layout

```
app/                  FastAPI web app (pages + candidate JSON API)
  questions.py        YAML schema + validating loader (mtime-cached)
  execution.py        HTTP client for the sandbox runner
  api/candidate.py    /api/questions, /api/run, /api/submit
runner/               execution sandbox service (own Docker image)
  runner_service/     executor (subprocess + rlimits), harness, FastAPI app
data/questions/       question bank (YAML) + example.yaml template
templates/, static/   UI (Monaco is vendored under static/vendor/monaco — no CDN)
tests/                pytest suite
```

## Testing & linting

```bash
uv run pytest                  # includes real-subprocess sandbox tests
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Code execution service is unavailable` in the UI | The runner container isn't healthy. `docker compose ps`, then `docker compose logs runner`. |
| Port 8000 already in use | Stop the other process, or edit the `ports:` mapping in `docker-compose.yml`. |
| Question edits don't show up | Ensure you edited `data/questions/` (bind-mounted) and refresh; check `docker compose logs app` for validation errors. |
| A question fails to load with a validation error | The app logs name the file and field; `example.yaml` documents every field. |
| Every test times out | The machine may be heavily loaded; raise `time_limit_seconds` in the question YAML. |
| Stale UI after rebuilding | Hard-refresh (Cmd-Shift-R); assets are cache-busted by file mtime, but the browser may cache the HTML. |
| Docker build fails pulling images | Check connectivity/registry access; the build needs the `python:3.12-slim` and uv base images once. |

## Security notes

This is a **local, single-user practice tool**: there is deliberately no
authentication, and it binds to localhost via the compose port mapping. Do not expose
it to an untrusted network. The sandbox is designed to stop accidents (infinite
loops, memory bombs, network calls) rather than a determined attacker with kernel
exploits.

## License

Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Derived from the GrillKit
project.
