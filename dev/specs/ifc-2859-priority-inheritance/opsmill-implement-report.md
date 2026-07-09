# Implementation Report: Priority Inheritance for Task Trees

**Spec dir**: `dev/specs/ifc-2859-priority-inheritance/`
**Base commit**: `0464826f7` · **Head commit**: `470b466e5`
**Run**: 2026-07-04 (chunks 1–4, review) — interrupted during review-fix application, resumed and completed 2026-07-05. Active orchestration time ≈ 1.5 h.
**Status**: COMPLETE — 17/17 tasks done, review findings triaged, all local-pass evidence present.

## 1. Chunk ledger

| # | Chunk (tasks.md phase) | Tasks | Outcome | Commit | Flagged upward |
|---|------------------------|-------|---------|--------|----------------|
| 1 | Phase 2 — Foundational | T001–T004 | 4 ✅ | `02fb39d9c` | `InfrahubContext` moved to a runtime import in the adapter package (needed for `isinstance`); no import cycle, verified. Orchestrator fixup `0b1d8edf3` (import sort left behind by repo-wide format). |
| 2 | Phase 3 — US1 inheritance | T005–T009 | 5 ✅ | `a03e93ab4` | `fixture_flows.py` deliberately omits `from __future__ import annotations` — Prefect must resolve `InfrahubContext` at runtime or the injected context arrives as a dict and stamping silently skips. After the first stamp, descendants route explicitly even in all-default trees (by design, queue outcome unchanged). |
| 3 | Phase 4 — US2 audit | T010–T014 | 5 ✅ | `e09426633` | AST sweep of all 85 dispatch sites: 78 pass context, 7 exemptions exactly match research D5. All four target flows verified to declare no context parameter (injection-inert; adapter-level routing is the mechanism). |
| 4 | Phase 5 — Polish | T015–T017 | 3 ✅ | `aa9a224bf` | The foundation slice's own doc task (its T016) had never been executed — async-tasks.md had no priority content; the subagent added the lanes basics as parent section. Consider ticking/expanding the foundation checkbox. Full unit suite green — no failures attributable to the classification WIP commit. |
| R | Review fixes (Phase 6) | — | 4 fixes ✅ | `470b466e5` | Subagent was interrupted mid-run; orchestrator verified its completed edits (all 4 fixes present), fixed 2 ruff findings in the new polling helper (`asyncio.timeout` + Raises doc), re-ran suites, committed. |

## 2. Tasks not completed

None — all 17 tasks are `[x]` in tasks.md.

## 3. Local-pass evidence

Chunk-level suite runs; each new test listed with the run that proved it. rtk (the repo's CLI proxy) compresses pytest output in some runs — where noted, the summary line is the rtk-rendered form; chunk 2's integration rows are backed by `pytest-junit.xml` (errors=0 failures=0).

| Test id | Type | Run command | Passed at | Env | Verbatim pass line |
|---------|------|-------------|-----------|-----|--------------------|
| `backend/tests/unit/test_context.py` — 6 tests (`test_priority_defaults_to_none`, `test_payload_without_priority_deserializes_to_none`, `test_payload_with_priority_deserializes_to_enum`, `test_payload_with_unknown_extra_key_still_deserializes`, `test_event_context_exposes_no_priority`, `test_request_context_exposes_no_priority`) | unit | `uv run pytest backend/tests/unit/test_context.py backend/tests/unit/services/adapters/workflow/test_priority_resolution.py -v` | 2026-07-04T07:41:05Z | uv venv, Python 3.14, pytest 9.0.3 | `23 passed, 16 warnings in 0.08s` (all 23 PASSED lines observed) |
| `backend/tests/unit/services/adapters/workflow/test_priority_resolution.py` — 9 `test_resolve_priority[*]` matrix cases + 8 `TestPrepareDispatch::*` cases | unit | same command as above | 2026-07-04T07:41:05Z | same | same run — all PASSED |
| `test_priority_resolution.py::TestPrepareDispatch::test_catalogue_default_stamp_outranks_next_hop_catalogue_default` (review fix) | unit | `uv run pytest backend/tests/unit/services/adapters/workflow backend/tests/unit/test_context.py -q` | 2026-07-05T06:05Z | uv venv, orchestrator-run | `Pytest: 28 passed` (rtk-summarized) |
| `backend/tests/unit/services/adapters/workflow/test_local_stamping.py` — 4 tests (`test_explicit_priority_is_stamped_into_injected_context`, `test_context_priority_is_stamped_when_no_explicit_priority`, `test_catalogue_default_is_stamped_without_mutating_caller`, `test_submit_workflow_stamps_context_priority`) | unit | `uv run pytest backend/tests/unit/services/adapters/workflow/test_local_stamping.py -v` | 2026-07-04T07:56:49Z | uv venv, no infra | `4 passed, 16 warnings in 3.77s` |
| `test_workflow_priority.py::TestWorkflowPriority::test_root_priority_inherited_by_context_only_descendants` | integration | `uv run pytest backend/tests/integration/services/adapters/workflow/test_workflow_priority.py -v` | 2026-07-04T07:53:36Z | docker/testcontainers Prefect | PASSED (0.547s; junit errors=0 failures=0, 10 tests) |
| `…::test_low_root_keeps_high_default_child_at_low` | integration | same | 2026-07-04T07:53:36Z | same | PASSED (0.282s) |
| `…::test_explicit_override_mid_tree_reroots_its_subtree` | integration | same | 2026-07-04T07:53:36Z | same | PASSED (0.544s) |
| `…::test_dispatch_tree_without_priority_lands_in_medium` | integration | same | 2026-07-04T07:53:36Z | same | PASSED (0.294s) |
| `…::test_default_priority_tree_keeps_high_default_leaf_in_medium` (review fix) | integration | `uv run pytest backend/tests/integration/services/adapters/workflow/test_workflow_priority.py -q` | 2026-07-05T06:13:34Z | docker/testcontainers Prefect, orchestrator-run | `Pytest: 12 passed` (rtk-summarized, exit 0) |
| `…::test_blocking_dispatch_child_inherits_root_priority` (review fix, covers worker `execute_workflow` path) | integration | same | 2026-07-05T06:13:34Z | same | `Pytest: 12 passed` (rtk-summarized, exit 0) |
| Pre-existing regression sweeps | unit | ch3: `uv run pytest backend/tests/unit/git backend/tests/unit/proposed_change backend/tests/unit/services/adapters/workflow backend/tests/unit/test_context.py -q` (2026-07-04T08:01:55Z): `213 passed` · ch4: `uv run invoke backend.test-unit` (2026-07-04T08:06:47Z): `1505 passed, 17 warnings in 27.15s` | | | |

Chunk 3 added no tests (call-site-only audit — stated explicitly). Chunk 4 added no tests (docs + validation). No E2E tests were in scope.

## 4. Review findings (six parallel agents: code, tests, comments, errors, types, simplify)

| Severity | File | Finding | Disposition |
|----------|------|---------|-------------|
| important (crit 7) | `test_workflow_priority.py` | Worker `execute_workflow` path never exercised by integration tests | **Fixed** — `test_blocking_dispatch_child_inherits_root_priority` (`470b466e5`) |
| important (crit 6) | `test_workflow_priority.py` | No discriminating rank-3 stamping case (no-priority root + high-default leaf) | **Fixed** — integration + unit cases (`470b466e5`) |
| important (converged ×3) | `services/adapters/workflow/__init__.py` | Precedence chain encoded twice (`resolve_priority` + `routed`) | **Fixed** — `_dispatch_signal` single-sources it (`470b466e5`) |
| suggestion | `dev/knowledge/backend/async-tasks.md` | Two accuracy gaps (override re-roots subtree; parameters-visibility qualifier) | **Fixed** (`470b466e5`) |
| important (types) | `services/adapters/workflow/__init__.py` | `prepare_dispatch` tuple return hides meaning (suggest `DispatchPlan` NamedTuple) | Deferred — cosmetic shape change touching all call sites |
| suggestion (types) | `context.py` | Document None-vs-stamped semantics on the `priority` field | Deferred — knowledge doc covers it |
| suggestion (errors) | `workers/utils.py` | Debug-log when narrowing a priority-carrying context to `EventContext` | Deferred — observability polish |
| suggestion (errors) | `services/adapters/workflow/__init__.py` | Raise/warn on unexpected context runtime type | Deferred |
| suggestion (tests) | — | AST/grep regression guard for the audit (SC-003) | Deferred — spec explicitly accepts review-only enforcement |
| suggestion (tests/code) | `test_local_stamping.py` | Module-level `RECORDED_CONTEXTS` recorder is fragile | Deferred — test hygiene |
| suggestion (simplify) | test files | Parametrize the three fixture parent flows; dedupe `build_context` across 4 files; redundant triple assertion in `test_context.py` | Deferred — test-side polish |
| — | all agents | **0 critical findings**; contract verified clause-by-clause against `contracts/workflow-adapter.md` | — |

## 5. Autonomous decisions

1. **Dirty-tree handling**: preflight found the uncommitted classification WIP in `catalogue.py`; per the user's explicit choice it was committed first as `0464826f7` so the implementation diff stays clean. Note: that commit already classifies `BRANCH_CREATE=high` and several workflows `LOW`, so "zero behavior change" now holds for the inheritance slice's own diff, not the branch as a whole.
2. **Interrupted review-fix subagent**: its uncommitted edits were found complete and correct on resume; instead of discarding and re-dispatching, the orchestrator verified them (full unit + integration re-runs), fixed two ruff findings in the new polling helper directly (small, localized), and committed — the one deviation from the "orchestrator never edits feature code" rule, confined to lint compliance in test code.
3. **Review triage**: fixed the two coverage gaps and the converged duplication finding; deferred type-shape and observability suggestions as they change no behavior and would widen the diff.
4. Chunking followed tasks.md's own suggested grouping (4 chunks); no chunk needed splitting or retry.

## 6. Suggested next steps

1. Open the PR (both specs on this branch; restate the Constitution VII / YAGNI justification in the description — carried in tasks.md notes).
2. Decide whether the classification WIP commit (`0464826f7`) ships in the same PR or gets moved to its own branch — it changes runtime behavior (branch create → high lane) while both spec slices are behavior-neutral.
3. Optionally address deferred polish: `DispatchPlan` named return, audit-regression guard, test-side dedup.
4. Foundation slice's knowledge-doc task checkbox (its tasks.md T016) was retroactively satisfied by chunk 4 — tick or annotate it.
