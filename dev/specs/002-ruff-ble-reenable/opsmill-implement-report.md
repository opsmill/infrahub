# Implementation Report: Re-enable ruff BLE (blind-except) rule

**Spec dir**: `specs/002-ruff-ble-reenable` (`dev/specs/002-ruff-ble-reenable`)
**Base commit**: `9247c6763037f8158e0f192fc5f8cb69581a2118` (merge-base with `origin/develop`)
**Head commit**: `06fd34d83ee89873db82009040c921da3d07bcd8`
**Prep + implement wall-clock**: 2026-07-22 07:25:11 UTC → 08:57:04 UTC (~1h32m, across prep + all 6 implementation phases)
**This run (verification + review + report)**: 2026-07-22 ~09:00 UTC → 09:34 UTC

**Context for this run**: this is the third `speckit.opsmill.implement` invocation for this feature. Two prior runs (each a separate session) completed the entire implementation loop — all 22 tasks in `tasks.md` were already `[X]` and committed on entry (last commit `06fd34d83`, "Polish: suppression audit, unit suite, SC-007 diff audit, quickstart replay"), and independent confirmation that BLE is removed from `pyproject.toml`'s ignore list and `ruff check --select=BLE .` is clean. Both prior runs were killed mid-review-phase before writing a final report. This run's job was: verify the inherited state fresh (not just trust it), re-run every verification gate independently, investigate a reported "pytest component-test collection issue" from scratch, execute the review phase, and produce this report. No new implementation chunks were dispatched — Phase 5 was already complete.

---

## 1. Chunk-by-chunk ledger

All chunks below were implemented and committed by prior (killed) sessions. I did not re-dispatch them; I independently re-verified their end state (gates, diffs, tests) rather than trusting the inherited commits at face value. Per-chunk "decisions flagged upward" are reconstructed from commit messages/diffs since the original subagents' live reports were lost when those sessions were killed.

| # | Chunk (tasks.md phase) | Tasks | Outcome | Commit(s) | Notes |
|---|------------------------|-------|---------|-----------|-------|
| 1 | Phase 1: Setup | T001 | ✅ 1/1 | `e24482113` | Re-measured inventory: 78/78 sites reconciled against data-model.md, no drift, no new sites. |
| 2 | Phase 3: US3 — SUPPRESS batches (part 1) | T002–T004 | ✅ 3/3 | `0c1a9bdaa` | Migrations Batch A (30 sites across m014–m074 + shared.py) — annotation-only. |
| 3 | Phase 3: US3 — SUPPRESS batches (part 2) | T005–T007 | ✅ 3/3 | `5b438fe6e` | Auth Batch B (8 sites) + runtime/infra Batch C (16 sites) — annotation-only. |
| 4 | Phase 3: US3 — SUPPRESS batches (part 3) + checkpoint | T008–T010 | ✅ 3/3 | `7ee067033` | Test-helper Batch D (7 sites) + tooling Batch E (9 sites) + US3 story checkpoint green. |
| 5 | Phase 4: US2 — NARROW batches + checkpoint | T011–T014 | ✅ 4/4 | `68ca27a21` | 8 sites narrowed (schema-branch test helper ×4, git conftest poll loops ×2, release.py version probes ×2); US2 checkpoint: 0 BLE violations repo-wide. |
| 6 | Phase 5: US1 — enforcement flip | T015–T018 | ✅ 4/4 | `f648739a7` | `"BLE"` removed from `pyproject.toml` ignore list; changelog fragment added; full-gate + canary-mutation checks green. |
| 7 | Phase 6: Polish | T019–T022 | ✅ 4/4 | `06fd34d83` | Suppression audit, unit suite, SC-007 diff audit, quickstart replay recorded. |

**Totals**: 22/22 tasks ✅, 0 ⚠️, 0 ❌.

No fixup commits were needed — all `tasks.md` checkboxes were already `[X]` and matched the actual diff on inspection.

---

## 2. Tasks not completed

None. All 22 tasks (`T001`–`T022`) are `[X]` in `tasks.md` and verified against the actual repo state.

---

## 3. Verification gates re-run this session (fresh evidence, not inherited)

All commands below were re-run independently in this session (not assumed from prior commits):

| Gate | Command | Result |
|------|---------|--------|
| BLE violations (repo, excl. submodule) | `ruff check --select=BLE . --exclude python_sdk` | 0 violations, exit 0 |
| BLE violations (bare, incl. submodule) | `ruff check --select=BLE .` | 4 findings — all in `python_sdk/infrahub_sdk/ctl/utils.py` (separate repo, out of scope; matches the discrepancy already documented in the `f648739a7` commit) |
| BLE removed from ignore list | `grep -n '"BLE"' pyproject.toml` | no match |
| Full backend lint | `invoke backend.lint` (ruff + ty + mypy) | all green, 1502 source files, 0 mypy issues |
| Full repo ruff check | `ruff check . --exclude python_sdk` | exit 0 |
| Full repo ruff format check | `ruff format --check --diff --exclude python_sdk .` | exit 0 |
| Bare-except backstop | `ruff check --select=E722 .` | 0 violations |
| Suppression audit | `grep -rn "noqa: BLE001" --include="*.py" . --exclude-dir=python_sdk --exclude-dir=.venv \| wc -l` | 70 (matches data-model.md SUPPRESS total exactly) |
| SC-007 diff audit | `git diff <base>..HEAD -- migrations/ auth.py oauth2.py oidc.py auth/` + line-level classification of every `+`/`-` line | every added line is a comment or a `# noqa: BLE001`-appended except line; every removed line is the pre-image of one of those same except lines — confirmed annotation-only |
| Enforcement canary (SC-006) | planted `except Exception: pass` in `tasks/utils.py`, ran `ruff check --select=BLE tasks/utils.py`, reverted | exactly 1×BLE001 reported; `git status` clean after revert |
| tasks/release.py narrow sanity | `python -c "from packaging.version import Version; Version('1.2.3-foo')"` | raises `InvalidVersion` as expected |
| tasks/release.py import sanity | `invoke --list` | exit 0, imports OK |
| Full backend unit suite (regression, SC-005) | `invoke backend.test-unit` | **1846 passed**, 32.19s |
| Two previously-flagged component tests | see §4 | **12 passed**, 44.33s |

### On the "pytest component-test collection issue"

Investigated fresh, per instructions, without assuming the prior runs' diagnosis. Root cause: **not a real pytest or code problem.** This repo's shell hook rewrites bare `pytest`/`uv run pytest` invocations through an `rtk` (Rust Token Killer) CLI proxy that summarizes pytest output to save tokens. In this session, that summarizer intermittently printed `Pytest: No tests collected` for these two files even when the underlying run fully succeeded. Bypassing the summarizer with `rtk proxy uv run pytest ...` (raw, unfiltered) on the identical command showed the true result every time: 12 items collected, 12 passed, exit 0 — reproduced 3 times (once via `--collect-only`, once via the hook-wrapped path directly, once via `rtk proxy` running the tests for real). A prior session was apparently misled by the summarizer's false-negative text into believing collection was broken. No code change was needed or made.

### Deferred by design (pre-existing decision, not a gap introduced by this run)

The two `except httpx.HTTPError:` narrowings in `backend/tests/integration/git/conftest.py` (T012, lines 31 and 53) back 5 integration test files (`test_auth_and_access.py`, `test_git_repository.py`, `test_delete_git_branch_gogs.py`, `test_readonly_repository.py`, `test_git_live_remote.py`) that require a live Gogs container over HTTP. `quickstart.md` §"CI-only verification (accepted)" and `data-model.md` Batch D already document this as intentionally deferred to CI's integration tier, with an explicit fallback (revert those 2 sites to SUPPRESS) if CI shows a gap. I did not attempt to stand up Gogs locally to force this — that was a considered planning-phase decision, not something left open by accident, and re-deciding it under this run would be scope creep. See §6.

---

## 4. Local-pass evidence

No new tests were added (per spec FR-008 — "no new tests are written; verification is lint-gate + existing-suite based"). Two existing test files had their exception-handling narrowed (T011); one fixture file used by 5 integration tests was narrowed (T012). Evidence for each:

| Test id | Type | Run command | Passed at (UTC) | Environment context | Verbatim pass line |
|---------|------|--------------|------------------|----------------------|---------------------|
| `backend/tests/component/core/schema/schema_branch/test_process_idempotency.py::test_process_idempotency` | component | `uv run pytest backend/tests/component/core/schema/schema_branch/test_process_idempotency.py backend/tests/component/core/schema/schema_branch/test_uniqueness_propagation.py` | 2026-07-22T09:17:15Z | Neo4j 2026.05.0-enterprise via testcontainers (image cached locally), Python 3.14.4, pytest-9.0.3 | `PASSED [ 8%]` |
| `backend/tests/component/core/schema/schema_branch/test_process_idempotency.py::test_process_idempotency_after_db_roundtrip` | component | (same command) | 2026-07-22T09:17:15Z | (same) | `PASSED [ 16%]` |
| `backend/tests/component/core/schema/schema_branch/test_uniqueness_propagation.py::TestSchemaProcessUniquenessIdempotent` (10 test methods) | component | (same command) | 2026-07-22T09:17:15Z | (same) | `PASSED` ×10, full session: `12 passed, 16 warnings in 44.33s` |
| `backend/tests/integration/git/conftest.py` poll-loop narrowings (back `test_auth_and_access.py`, `test_git_repository.py`, `test_delete_git_branch_gogs.py`, `test_readonly_repository.py`, `test_git_live_remote.py`) | integration | `uv run pytest backend/tests/integration/git` (CI integration tier) | deferred — local integration run requires a live Gogs container over HTTP; pre-existing planning decision (quickstart.md "CI-only verification (accepted)", data-model.md Batch D) to verify this tier in CI only, with a documented SUPPRESS fallback if CI disagrees | n/a locally | n/a |
| Full backend unit suite (regression check — no test files in this suite were modified by this feature; run as SC-005 evidence that the SUPPRESS/NARROW edits caused no regressions) | unit | `uv run invoke backend.test-unit` | 2026-07-22T09:2{0-1}:00Z (immediately following the component-test run) | Python 3.14.4, pytest-9.0.3, no DB required | `1846 passed, 17 warnings in 32.19s` |

No `MISSING` rows. The one `deferred` row is a pre-existing, documented project decision (see §6), not an omission from this run.

---

## 5. Review findings

Two review agents ran in parallel across the full feature diff (`9247c676..06fd34d83`, 46 implementation files): **error-handling** (`speckit-review-errors`) and **simplification** (`speckit-review-simplify`). Both were instructed on the feature's design intent (SUPPRESS = annotation-only, NARROW = 8 specific sites) and given `data-model.md` as ground truth, so they could distinguish "diff doesn't match its own claim" from "pre-existing/accepted behavior working as designed."

No CRITICAL or HIGH findings from either agent — nothing met the bar for an inline fix.

| Severity | File:Line | Summary | Agent | Disposition |
|----------|-----------|---------|-------|-------------|
| MEDIUM | `backend/tests/integration/git/conftest.py:53` | Narrowed `except httpx.HTTPError:` doesn't cover `json.JSONDecodeError`/`KeyError` from `resp.json()["sha1"]` on a malformed 201 body — could turn a transient Gogs-startup race into a hard failure instead of a retry | error-handling | **Deferred, not fixed.** Already documented and explicitly accepted in `data-model.md` Batch D and `quickstart.md` ("medium confidence — fallback is SUPPRESS") during planning, with a stated fallback. Re-opening an already-critiqued planning tradeoff during implement-review would be scope creep; recorded here for visibility per instructions, matches CI-deferral in §3/§6. |
| LOW | `test_process_idempotency.py:159,165`, `test_uniqueness_propagation.py:43,49` | `except SchemaNotFoundError:` doesn't also catch the `ValueError` that `SchemaBranch.get()` can raise when a cache entry exists but its hash is missing | error-handling | **Deferred.** Verified impact is negligible: `_describe_hash_diff(...)` is only evaluated inside an already-failed `assert`'s message expression, so worst case is a less-helpful traceback on a test that was already red — not a masked defect or false pass. |
| LOW | `m059_fix_hfid_display_label_nulls.py:238,248` | Two adjacent `except` blocks (9 lines apart) share byte-identical justification comment text despite guarding different computations (`display_label` vs `human_friendly_id`), making the two `grep` hits indistinguishable | simplify | **Deferred** (advisory-only per skill scope; no behavior impact). |
| LOW | 4 files: `message_bus/operations/__init__.py:34`, `core/validators/tasks.py:85`, `tests/helpers/test_worker.py:107`, `tests/integration_docker/test_merge_kill_recovery.py:85` | New justification comments run 124–139 chars, wider than the files' normal ≤120-char wrap (still under the 150-char E501 ceiling, so lint-clean) | simplify | **Deferred** (cosmetic only). |
| LOW | `tests/integration_docker/test_merge_kill_recovery.py:85-89` | New one-line justification comment overlaps in content with the pre-existing 3-line body comment above the same `except` | simplify | **Deferred** (advisory; T008 explicitly instructed keeping the existing comment verbatim and only adding the new one). |
| info | `test_process_idempotency.py` / `test_uniqueness_propagation.py` — duplicated `_describe_hash_diff` helper | Pre-existing duplication (confirmed via `git show` against pre-image commits, predates this feature by several commits); this diff only touched the narrowed `except` line in both copies | simplify | Out of scope for this feature — noted for awareness only, not a finding against this diff. |

**Verdicts from the two agents**: error-handling — "the diff delivers truthful, zero-behavior-change suppressions for all 70 sites and safe narrowings for 6 of 8; the remaining 2 NARROW sites... narrow to a real but demonstrably incomplete exception type — genuine low/medium-severity gaps confined to test code, not a broken delivery of the feature's core claim." Simplify — "clean, mechanical, and highly consistent — the only nits are two cosmetic wording/wrapping items and one pre-existing (untouched) duplication noted for awareness."

No fixes were applied as a result of this review (nothing cleared the high-severity bar); HEAD remains `06fd34d83`, no new commit was needed for this phase.

---

## 6. Autonomous decisions

- **Did not re-dispatch Phase 5.** Two prior sessions already completed and committed all 22 tasks before this run started. Rather than trusting that inherited state, I independently re-ran every gate in `quickstart.md` fresh (§3) and re-derived the SC-007 diff-audit and suppression-count evidence myself rather than citing the prior commits' own claims about themselves.
- **Diagnosed, rather than assumed, the "pytest component-test collection issue."** Per instructions not to trust the prior runs' in-progress diagnosis, I reproduced it, bypassed the `rtk` CLI proxy's output filtering, and confirmed it was a summarizer false-negative (`Pytest: No tests collected` shown even on a fully passing run), not a real collection defect. No code change was made; this affects only how test output is read in this session's tooling, not the codebase.
- **Left the conftest.py `httpx.HTTPError` gap unfixed.** The error-handling reviewer flagged a real, but already-known-and-accepted, residual risk (§5). Since it was already surfaced and deliberately accepted during the critique/planning phase (with a documented fallback), and doesn't meet the "high severity or above" auto-fix bar, I recorded it rather than patching it, to avoid re-litigating a planning decision mid-review.
- **Did not attempt local Gogs-backed integration test execution.** The project's own quickstart.md already scopes this to "CI-only verification (accepted)." Standing up Gogs locally to second-guess an already-accepted plan decision would be scope creep for a review-and-report run; flagged here so a human can confirm the call still stands.
- **Ran the two review agents in parallel**, not sequentially. Both are read-only/advisory (no file edits), so unlike Phase 5 implementation chunks there's no shared-write conflict risk from concurrency.

---

## 7. Suggested next steps

1. Open a PR — the feature is complete, all gates are green, and no review finding met the bar for a blocking fix.
2. Optional polish (all advisory, non-blocking, listed in §5): disambiguate the two identical `m059` justification comments; rewrap the 4 over-120-char comments; trim the redundant sentence in `test_merge_kill_recovery.py`; widen the two `SchemaNotFoundError` catches to also catch `ValueError` if a cleaner diagnostic on already-failing tests is wanted.
3. Watch CI's integration tier for `backend/tests/integration/git/*.py` after merge. If either narrowed poll loop in `conftest.py` (lines 31/53) starts failing hard instead of retrying through a Gogs-startup race, fall back to the documented SUPPRESS treatment for those 2 sites per `data-model.md` Batch D — the code is correct either way (rollback note in `quickstart.md`).
