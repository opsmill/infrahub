# Implementation Report: Priority-aware API backpressure (server-side)

**Status**: ✅ COMPLETE

## 1. Header

- **Feature**: Priority-aware API backpressure (server-side) — Jira IFC-2886
- **Spec dir**: `specs/ifc-2886-priority-api-backpressure/`
- **Base commit**: `e259e9453` (prep artifacts, pre-implementation)
- **Head commit**: `a2d3ccbb9`
- **Change size**: 22 files, +1653 / −29
- **Tasks**: 27/27 complete (all `[X]`)
- **Tests**: 42 passing (34 unit + 8 component); +5 added during review
- **Wall-clock**: ~1h of subagent execution across 8 implementation chunks + 1 review-fix chunk (approx; single-session).

## 2. Chunk-by-chunk ledger

| # | Chunk (phase) | Tasks | Outcome | Commit(s) | Notes flagged upward |
|---|---------------|-------|---------|-----------|----------------------|
| 1 | Phase 1 Setup | T001–T004 (4) | ✅×4 | `1962d12` | `uv lock` re-resolution normalized two unrelated `pendulum` markers (artifact, not authored). `prometheus-client` pinned `>=0.25,<0.26` (no version bump). |
| 2 | Phase 2 Foundational | T005–T010 (6) | ✅×6 | `0267a5a` | `Acquisition.release()` idempotent; `Priority.label` property; `build_admission_controller()` factory; `multiprocess_mode` documented (not set); CoDel is a mutable state machine. |
| 3 | Phase 3 US2 (header) | T011–T012 (2) | ✅×2 | `2b36da4` | Parser keys on enum member names, catches `KeyError` for invalid/empty. Added `backend/tests/unit/api/admission/__init__.py`. |
| 4 | Phase 4 US1 (MVP gradient) | T013–T017 (5) | ✅×5 | `a3952bb` | Middleware settings-free (controller injected). **Controller built at module-import in server.py** (flagged → fixed in review). Component tests need no DB (Prefect session fixture ~7s is harness overhead only). |
| 5 | Phase 5 US3 (429 shape) | T018–T019 (2) | ✅×2 | `da473f5` | Reason metric already counted in controller (no double-count). REST/GraphQL envelope selection by path prefix. |
| 6 | Phase 6 US4 (capacity) | T020–T021 (2) | ✅×2 | `46238cd` | Burst test pins "shorter than one interval" to an observed elapsed-time assertion. |
| 7 | Phase 7 US5 (observability) | T022–T023 (2) | ✅×2 | `504633f` | **Found + fixed a real gap**: `in_flight`/`waiters` gauges weren't re-synced on slot release; added `AdmissionController.release()` that syncs gauges. |
| 8 | Phase 8 Polish | T024–T027 (4) | ✅×4 | `d3576f4` | Changelog `+ifc-2886.added.md`; `docs.generate` regenerated `configuration.mdx` (+8 lines). SC-001 latency bound deferred (see §6). |
| R | Review fixes | (review) | ✅ | `a2d3ccb` | See §5. Suite 37→42. |

Every implementation chunk ran in a clean-context subagent; chunks ran strictly sequentially (never parallel). No chunk was reported `❌ blocked`; no chunk needed a re-dispatch or split.

## 3. Tasks not completed

None. All 27 tasks are `[X]` in `tasks.md`.

## 4. Local-pass evidence

All tests were observed passing locally. Environment (common): local worktree, Python 3.12.13, pytest 9.0.3, `asyncio_mode=auto`; **no external infra** (no Neo4j/Redis/NATS/testcontainers) — the admission layer is transport-only and its component tests use standalone `FastAPI()` apps + `httpx.ASGITransport`.

| Test id | Type | Run command | Passed at (ISO 8601) | Env context | Verbatim pass line |
|---------|------|-------------|----------------------|-------------|--------------------|
| `test_priority.py` (13 cases: high/normal/low, mixed-case, whitespace, empty, none, invalid×2, ordering, labels) | unit | `uv run pytest backend/tests/unit/api/admission/test_priority.py -v` | 2026-07-11T14:15:24Z | n/a | `13 passed in 0.04s` |
| `test_slot_pool.py` (priority handoff, within-class FIFO, cancel-while-queued no-leak, cancel-after-handoff re-release) | unit | `uv run pytest backend/tests/unit/api/admission/test_slot_pool.py backend/tests/unit/api/admission/test_codel.py -v` | 2026-07-11T14:27:41Z | n/a | `8 passed in 0.05s` |
| `test_codel.py` (sub-interval burst=0 drops, onset after 1 interval, single-below-target exit, high-target protection) | unit | (same as above) | 2026-07-11T14:27:41Z | n/a | `8 passed in 0.05s` |
| `test_capacity.py` (8 derive_max_concurrency cases incl. floor/fractional/identity) | unit | `uv run pytest backend/tests/unit/api/admission/test_capacity.py -v` | 2026-07-11T14:43:12Z | n/a | `8 passed in 0.04s` |
| `test_admission_middleware.py::test_gradient` + `test_all_admitted_when_capacity_available[high|normal|low]` | component | `uv run pytest backend/tests/component/api/test_admission_middleware.py -v` | 2026-07-11T14:27:46Z | n/a | `4 passed, 1 warning in 6.99s` |
| `test_admission_middleware.py::test_shed_backstop_returns_rest_envelope`, `::test_shed_codel_returns_429` | component | `uv run pytest backend/tests/component/api/test_admission_middleware.py -v` | 2026-07-11T14:39:45Z | n/a | `6 passed, 1 warning in 6.79s` |
| `test_admission_middleware.py::test_capacity_and_burst` | component | `uv run pytest backend/tests/component/api/test_admission_middleware.py -v` | 2026-07-11T14:43:21Z | n/a | `7 passed, 1 warning in 6.81s` |
| `test_admission_middleware.py::test_metrics` | component | `uv run pytest backend/tests/component/api/test_admission_middleware.py -v` | 2026-07-11T14:52:43Z (unit+component aggregate) | n/a | `37 passed, 1 warning in 5.85s` |
| `test_excluded_path_bypasses_admission[/health]`, `[/metrics]`, `test_kill_switch_passes_through`, `test_handler_exception_releases_slot`, `test_build_admission_controller_sets_gauge` (review-added) | component | `uv run pytest backend/tests/unit/api/admission/ backend/tests/component/api/test_admission_middleware.py -v` | 2026-07-11T15:08:54Z | n/a | `42 passed, 1 warning in 6.01s` |

**Final aggregate run** (post-review): `42 passed, 1 warning in 6.01s` at 2026-07-11T15:08:54Z. No `MISSING` rows. (The single warning is a pre-existing Starlette/httpx deprecation, unrelated to this change.)

### Not run locally (recorded, not blocking)

- **SC-001 discovery latency bound** (quickstart §4): requires a running server under induced overload. Deferred to a manual/CI step. Command: set `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE=4`, `INFRAHUB_API_BACKPRESSURE_CODEL_TARGET_SECONDS=0.005`, `INFRAHUB_API_BACKPRESSURE_CODEL_INTERVAL_SECONDS=0.1`, drive mixed high/low request streams, and scrape `/metrics` for `infrahub_admission_rejected_total{priority="low"}` climbing while `high`≈0 and read `infrahub_admission_sojourn_seconds` P99. This is a **discovery measurement**, not an added test — the executable proxy `test_gradient` already demonstrates SC-002 (high served while low sheds). This does not trigger the INCOMPLETE rule (it is not a `MISSING` unit/integration/e2e row).

## 5. Review findings (Phase 6)

Three parallel review lenses (correctness/concurrency, test-quality, types/errors/comments) ran across `e259e9453..d3576f4`. The concurrency core (slot pool cancellation-safety, CoDel semantics, controller accounting on non-cancelled paths, middleware short-circuit) was independently verified **correct**.

| Severity | File | Finding | Resolution |
|----------|------|---------|-----------|
| 🔴 High | `server.py` | Controller built at **module import** → `initialize_and_exit()` at import risks `sys.exit(1)` on bad env, and freezes settings so runtime/test overrides are ignored (breaks CORS-parity claim). | **Fixed** (`a2d3ccb`): construction moved to lazy stack-build inside `AdmissionMiddleware.__init__` (production path), injected controller kept for tests; gauge-set moved into `build_admission_controller()`; `import infrahub.server` no longer loads settings. |
| 🔴 High | tests | Excluded-path bypass (`/health`,`/metrics` must never shed) had **zero coverage**. | **Fixed**: added `test_excluded_path_bypasses_admission[/health]/[/metrics]`. |
| 🟠 Med-High | tests | Kill-switch (`enabled=False`) pass-through untested. | **Fixed**: added `test_kill_switch_passes_through`. |
| 🟠 Med-High | tests | Handler-exception slot release (FR-008 `finally`) untested at HTTP layer. | **Fixed**: added `test_handler_exception_releases_slot`. |
| 🟠 Med | `controller.py` | Unguarded Prometheus calls between `acquire()` and returning `Admitted` could leak a slot if one raises. | **Fixed**: wrapped acquire→return in `try/except: release(); raise`. |
| 🟠 Med | `metrics.py` | Multiprocess comment's causal claim ("wipe → per-worker") is wrong; plain Gauge is `multiprocess_mode="all"` when `PROMETHEUS_MULTIPROC_DIR` is set. | **Fixed**: comment rewritten to the real invariant. |
| 🟡 Med | tests | Real capacity wiring (`build_admission_controller`) was self-simulated. | **Fixed**: added `test_build_admission_controller_sets_gauge`. |
| 🟡 Low | `middleware.py` | Decision handling not exhaustive (`assert_never`). | **Fixed**: added `elif Rejected / else assert_never`. |
| 🟡 Low | tests | Spec-kit IDs (`M-1`, `M-6`, `FR-OBS-6`) in test docstrings violate code-doc-style. | **Fixed**: reworded to plain language. |
| ⚪ Low | `test_gradient` | Runs on the real clock with real sleeps → mild CI flake window on the all-`200` HIGH assertion. | **Deferred** (recorded). The forced-clock `test_shed_codel`/`test_metrics` cover the shed decision deterministically; `test_gradient` remains an integration smoke. |
| ⚪ Low | tests | Three-way NORMAL ordering (low→normal→high) not asserted end-to-end; only high-vs-normal at the controller level. | **Deferred** (recorded) — enhancement. |
| ⚪ Low | `controller.py` | Client-disconnect-while-queued makes `offered > admitted+rejected` transiently and leaves `waiters` gauge briefly stale (no slot leak). | **Deferred** (recorded) — would need a `cancelled` counter, beyond v1 spec scope. |
| ⚪ Low | `middleware.py` | Excluded-path match is prefix-only; `/metrics-internal`-style paths would also bypass (none exist today). | **Deferred** (recorded). |
| ⚪ Low | `middleware.py` | REST vs GraphQL shed envelopes are byte-identical today (`dict[str, Any]`); the branch is intentionally kept for future divergence. | **Deferred** (recorded). |

All High and Medium-High findings were fixed inline and committed (`a2d3ccb`); Low findings are recorded here and not blocking.

## 6. Autonomous decisions

- **Chunking**: one chunk per `tasks.md` phase heading (8 chunks); none exceeded the size thresholds so none were split, and no small adjacent phases were merged (per the strategy).
- **Commit mechanism**: the referenced `speckit-checkpoint-commit` skill is not installed in this repo; every chunk committed directly with git (safe — dedicated worktree branch `dga/feat-rate-limiting-api-zb38x`). No `--amend` of subagent commits.
- **Review fix routed to a subagent**: the High `server.py` fix spanned 3 files + needed 5 new tests, so it was dispatched as a fresh clean-context subagent rather than edited inline.
- **SC-001 discovery deferral**: accepted the subagent's call to defer the live-overload latency measurement to a manual/CI step (it needs a running stack), since it is a discovery measurement and `test_gradient` is the executable SC-002 proxy. Flagged here for the user to confirm.
- **`uv lock` artifact**: kept the two incidental `pendulum` marker normalizations `uv lock` produced in chunk 1 (they are what uv actually resolves); revert if a minimal lock diff is preferred.
- **`Callable` import location**: left as `from typing import Callable` (switching to `collections.abc` triggered ruff TC003 requiring TYPE_CHECKING restructuring) — kept lint-clean.

## 7. Suggested next steps

1. **Open a PR** for branch `dga/feat-rate-limiting-api-zb38x` (9 commits, base `stable`). Flag the governance items in the description: new `X-Priority` header + `429` behaviour (API surface), admission middleware consuming a client-controlled header (borderline auth), and the new `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE` config value (default 100 preserves current driver behaviour).
2. **Run the SC-001 discovery scenario** against a live instance (commands in §4 / quickstart §4) to quantify the headline latency bound and confirm the sojourn signal rises under real overload (critique E1 acceptance gate).
3. **Sequence the rollout** with the frontend `X-Priority: high` ticket: until the frontend sends `high`, interactive traffic is `normal` and shed like background under overload — the `INFRAHUB_API_BACKPRESSURE_ENABLED=false` kill-switch is the safe rollback.
4. **Optional hardening** (deferred low-severity): make `test_gradient` clock-deterministic, add the three-way NORMAL-ordering assertion, and consider a `cancelled` counter for the client-disconnect accounting edge.
5. Before pushing, run `/pre-ci` (format, lint, generated-doc validation) — the regenerated `configuration.mdx` is already committed so the `validate-generated-documentation` job should pass.

---

*Generated by `speckit-opsmill-implement`. Implementation executed via clean-context subagents, one per chunk; reviewed across the full diff; High/Medium-High findings fixed inline.*
