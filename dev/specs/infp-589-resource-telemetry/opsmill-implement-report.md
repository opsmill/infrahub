# Implementation Report: Licensing Resource-Allocation Telemetry

**Status: DONE**

| | |
|---|---|
| Feature | Licensing resource-allocation telemetry (per-component CPU/RAM) |
| Spec dir | `dev/specs/infp-589-resource-telemetry` (`specs/` → symlink) |
| Branch | `resource-telemetry-infp-589` (stacked on `telemetry-collection-infp-589`) |
| Base commit | `edda6001e` |
| Head commit | `37c6c0944` |
| Commit mode | Scoped orchestrator commits (per user) — feature paths only; unrelated not-ours working-tree files never staged |
| Local test env | macOS; Python 3.14.5; testcontainers Neo4j reachable (`DOCKER_HOST` socket) — component tests ran locally, not deferred |

## Chunk-by-chunk ledger

| # | Chunk (phase) | Tasks | Outcome | Commit | Notes flagged upward |
|---|---------------|-------|---------|--------|----------------------|
| 1 | Setup + Foundational | T001–T007 (7) | 7 ✅ | `30ec63988` | ProcessResources injected as `attrs` Factory-default (sanctioned transitional shape); cgroup v1 unlimited-memory sentinel via `2**62`; E1 verified (resources key reuses identity). |
| 2 | US1 (MVP) | T008–T011 (4) | 4 ✅ | `ee3216036` | `workers.total==2` in the test required reusing worker identities across git_agent/api_server keys (list_workers counts distinct identities). |
| 3 | US2 (air-gapped) | T012–T013 (2) | 2 ✅ | `1be0d4558` | T013 verification-only — `gather()` builds the full payload before the store/opt-out branch; no code change. Test never POSTs (opt-out=true). |
| 4 | US3 (degradation) | T014–T015 (2) | 2 ✅ | `cb249bc90` | T015 found + fixed a gap: the DB `processor_assigned` read caught only `Neo4jError`, so a driver-side failure could escape `gather()`; wrapped it in `safe_metric`. |
| 5 | Polish | T016–T019 (4) | 4 ✅ | `d76faed21` | E1 regression test; changelog + FAQ describe the *actual* extend-in-place shape (task text said "resources block"). `invoke lint` exit 1 only from `yamllint` on gitignored local dirs — out of scope; `backend.lint` (ruff/ty/mypy) clean. |
| — | Review fixes (Phase 6) | — | — | `37c6c0944` | See Review findings. |

## Tasks not completed

None — T001–T019 are all `[X]` in `tasks.md`.

## Local-pass evidence

Docker was available, so **all** tests (unit + component) executed locally and passed — no deferred/MISSING rows.

| Test id (file / group) | Type | Run command | Passed at (ISO 8601) | Environment | Verbatim pass line |
|---|---|---|---|---|---|
| `backend/tests/unit/telemetry/test_resources.py` (cgroup/host reader; 21 cases) | unit | `uv run pytest backend/tests/unit/telemetry/` | 2026-07-21T16:16Z | pure; no services | `63 passed` (whole unit dir, final) |
| `backend/tests/unit/telemetry/test_aggregation.py` (dedup/sum/undercount/null + failed-read drop; 8) | unit | `uv run pytest backend/tests/unit/telemetry/` | 2026-07-21T16:2x Z (post-review) | pure | `63 passed` |
| `backend/tests/unit/telemetry/test_database.py` (`_worker_limit_from_value`; 7 cases) | unit | `uv run pytest backend/tests/unit/telemetry/` | 2026-07-21T16:2x Z (post-review) | pure | `63 passed` |
| `backend/tests/component/telemetry/test_resources.py` (aggregate+server dedup, backward-compat, opt-out, 4× degradation, E1 count-invariant; 8 tests) | component | `DOCKER_HOST=… uv run pytest backend/tests/component/telemetry/` | 2026-07-21T16:2x Z (post-review) | testcontainers Neo4j + Prefect harness | `44 passed` (whole telemetry component suite, final) |

Final orchestrator-run verification after the review fixes: unit `63 passed`, telemetry component `44 passed`, `uv run invoke format` clean, `ruff`+`mypy` on changed modules clean.

## Review findings (Phase 6 — 4 lenses: code, errors, types, tests)

No Critical. Importants fixed inline; Suggestions triaged.

| Severity | Area | File | Summary | Disposition |
|---|---|---|---|---|
| Important | correctness (code+types converged) | resources.py | A failed self-read (all-null reading) nulled the **whole fleet** aggregate instead of undercounting | **Fixed** — `aggregate()` drops all-null readings before summing; unbounded (`processor_assigned=None` on a healthy host) still nulls that one field |
| Important | error-handling + tests | database.py | `get_processor_assigned` swallowed `Neo4jError` silently (shadowing the `safe_metric` logger); positive-value path untested | **Fixed** — removed the internal catch (safe_metric now logs); extracted pure `_worker_limit_from_value` + unit tests (300/0/-1/abc/None) |
| Suggestion | error-handling | resources.py | `_read_text_file` caught `OSError` but not decode errors (`ValueError`) → could null the whole reading | **Fixed** — catches `(OSError, ValueError)` |
| Suggestion | error-handling | component.py | Failed-read fallback called `socket.gethostname()` outside the guard → could itself break the heartbeat | **Fixed** — uses a host sentinel; removed now-unused `socket` import |
| Suggestion | comments | component.py | Retry-rationale comment named a failure mode the retry can't reach | **Fixed** — comment corrected |
| Suggestion | spec-alignment | spec.md, research.md | "zero workers → 0 (measured-empty)" contradicted the shipped `null` | **Fixed** — docs reconciled to `null` |
| Suggestion | observability | resources.py | cgroup→psutil fallback is silent; a future path typo would over-report host memory undetectably | Deferred — add a one-time debug log of which source won |
| Suggestion | types | component.py, tasks.py | `"api_server"`/`"git_agent"` magic strings in 4 places (no shared `Literal`/constant) | Deferred |
| Suggestion | types | tasks.py | `_resource_fields` dict-splat into models bypasses static field checking | Deferred |
| Suggestion | tests | component test | `read_worker_resources` malformed-entry / non-matching-key skip branches untested | Deferred |
| Important (PRE-EXISTING) | error-handling | tasks.py / database.py | `gather_database_information` / `get_system_info` (JMX) are **not** `safe_metric`-wrapped — a full DB/JMX failure aborts the whole snapshot (predates this feature) | Out of scope — flagged as follow-up (do not drive-by refactor existing code) |

## Autonomous decisions

- **Chunk boundaries**: merged the 1-task Setup phase into Foundational (a lone scaffold file is not a meaningful review unit); otherwise one chunk per `tasks.md` phase.
- **Commits**: per the user's choice, subagents implemented + tested but did **not** commit; the orchestrator committed each chunk scoped to explicit feature paths, so the unrelated not-ours working-tree files (`.claude/settings.json`, `development/docker-compose-database-neo4j.yml`, `changelog/+neo4j-heap-defaults.fixed.md`, `dev/skills/*`, `repositories/`, `.specify/feature.json`) were never staged and the review diff stayed clean.
- **Subagents implemented directly** (did not invoke `speckit-implement`) to guarantee no self-commit under the scoped-commit policy.
- **Review scope**: ran the 4 correctness-critical lenses (code/errors/types/tests) in parallel; skipped `comments` (the code-doc-style rule was enforced + verified each chunk) and `simplify` (advisory polish).
- **One existing test fixture corrected**: the "unbounded host" case used an unrealistic all-null reading; updated to a realistic healthy-but-unbounded reading (the exact distinction the fleet-null fix introduces).

## Suggested next steps

1. **Open a PR** for `resource-telemetry-infp-589` (base `telemetry-collection-infp-589` or `develop` once the parent merges) and run CI.
2. **Coordinate the payload-version bump** with the telemetry-receiving service before flipping `TELEMETRY_VERSION` (intentionally left unchanged this phase — research D13).
3. **Follow-ups** (deferred, non-blocking): wrap `gather_database_information` in `safe_metric` (pre-existing snapshot-abort risk); a `Literal`/constant for the component names; a one-time cgroup-source debug log; tests for the `read_worker_resources` skip branches.
4. The `processor_assigned` fields ship `null` until enforcement (INFP-472) sets the limits; the reads self-populate then with no code change.
