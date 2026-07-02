# Tasks: Multi-environment single-repo validation (Approach A)

**Input**: Design documents from `specs/001-multi-env-repo-tests/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/behavioural-contract.md, quickstart.md

**Nature of this feature**: the deliverable *is* tests. Every task writes a test, a test helper, or
test harness wiring — there is no separate product code. "Green" tasks assert working behaviour;
`xfail(strict)` tasks reproduce a tracked defect and are confirmed by *failing as predicted*.

**Code-doc-style gate**: no issue IDs (#9568 etc.) in any test name, docstring, or comment. Every
`xfail(strict, reason=...)` reason describes the behaviour, not the ticket.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- Deterministic-prong stories (US1, US3, US4, US5) all live in **one file**
  (`backend/tests/integration/git/test_multi_env_writeback.py`) → their test-writing tasks are
  **sequential** (same-file), not `[P]`, with respect to each other.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the deterministic-prong module `backend/tests/integration/git/test_multi_env_writeback.py` (module docstring describing the multi-environment write-back / branch-mapping behaviours under test; imports mirroring `backend/tests/integration/git/test_git_live_remote.py`)
- [ ] T002 [P] Create the full-stack module `backend/tests/integration_docker/test_multi_env_approach_a.py` with a class based on `TestInfrahubDockerClient` (mirror `backend/tests/integration_docker/test_propose_change_repository.py`). First determine how the existing `integration_docker` tests are kept out of the default CI run (dedicated Docker job vs. a marker); reuse that same mechanism. Only if the Docker job runs the whole directory unconditionally, add an opt-in marker and register it in `pyproject.toml` `[tool.pytest.ini_options].markers`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ Blocks the deterministic-prong stories (US1, US3, US4, US5).**

- [X] T003 Reuse the existing Gogs remote harness from `backend/tests/integration/git/conftest.py` (`gogs_server`, `create_gogs_repo`, `gogs_clone_url`) on the `TestInfrahubApp` base — the same setup `test_git_live_remote.py` uses; no new remote plumbing (write-back pushes are accepted by the Gogs server)
- [X] T004 [P] Add a repo-registration helper in `backend/tests/integration/git/test_multi_env_writeback.py` that issues `CoreRepositoryCreate` (with `default_branch`) / `CoreReadOnlyRepositoryCreate` (with `ref`) directly, setting the pin **at creation** (never create-then-update) — done inline via `client.create(kind=REPOSITORY, data={..., "default_branch": ...})`
- [ ] T005 [P] Add a deadline-bounded poll helper in `backend/tests/integration/git/test_multi_env_writeback.py` that waits on `client.branch.all()` and the repository's recorded `commit` (never `sync_status`, never a fixed sleep)

**Checkpoint**: local writable remote + registration + polling available → deterministic stories can begin.

---

## Phase 3: User Story 1 — Multi-worker write-back defect (Priority: P1) 🎯 MVP

**Goal**: Reproduce #9568 deterministically by reconstructing the failing worker-clone state.

**Independent Test**: run the file; the reproduction is `xfailed` (drop observed) and stays green-in-CI.

- [X] T006 [US1] Add `test_writeback_dropped_when_default_branch_absent_locally` in `backend/tests/integration/git/test_multi_env_writeback.py`: reconstruct a clone holding only local primary + `origin/<default>` (no local `<default>`), perform a write-back merge to `<default>`, assert `push` reports success **and** the remote `<default>` tip is unchanged; mark `xfail(strict, reason="write-back push silently dropped when the executing clone has no local default branch")`
- [X] T007 [US1] Run the test; confirm it `xfails` (drop reproduced). If it `XPASSes`, fix the clone-state reconstruction until the drop is observed — verified: `1 xfailed in 170.24s`

**Checkpoint**: MVP — the #9568 mechanism is reproduced deterministically and self-updates when fixed.

---

## Phase 4: User Story 3 — Non-main default, no phantom (Priority: P2)

**Goal**: Lock the #9601 guarantee (regression guard).

**Independent Test**: run the file; both US3 tests pass (green).

- [X] T008 [US3] Add `test_nonmain_default_maps_to_primary_no_phantom` in `backend/tests/integration/git/test_multi_env_writeback.py`: register a read-write repo with `default_branch=develop`, drive a sync cycle, assert `client.branch.all()` contains **no** standalone `develop` and that `develop` maps onto the primary branch (green)
- [X] T009 [US3] Add `test_nonmain_default_import_not_frozen` in the same file: land a new commit on remote `develop`, drive a sync, assert the repository's recorded `commit` advances to the new SHA (green)

**Checkpoint**: non-main default import behaviour is guarded.

---

## Phase 5: User Story 4 — Conflict & divergence resilience (Priority: P2)

**Goal**: Assert conflicts/divergence surface (never silently lost) and confirm two suspected defects.

**Independent Test**: run the file; US4 green tests pass and US4 defect tests `xfail`.

- [X] T010 [US4] Add `test_divergent_default_branch_pull_surfaces_and_recovers` in `backend/tests/integration/git/test_multi_env_writeback.py`: diverge the local `<default>` from the remote (out-of-band commit / force-reset), drive a pull/sync, assert the divergence surfaces as an error for that branch **and** the branch recovers on a subsequent sync — where "recovers" = a later sync of that branch advances its recorded `commit` (or re-imports it) with **no** manual git action against the worktree; `xfail(strict, reason="divergent pull leaves the worktree in a permanent conflicted state")`
- [X] T011 [US4] Add `test_nonff_writeback_not_silently_dropped` in the same file: advance remote `<default>` out-of-band after import, perform an in-Infrahub merge, assert the write-back either lands or is reported failed — not silently dropped; `xfail(strict, reason="non-fast-forward write-back push is silently swallowed")`
- [X] T012 [US4] Add `test_merge_conflict_surfaced_and_worktree_clean` in the same file: create a genuine content conflict between an Infrahub branch and `<default>`, merge, assert a failure is raised **and** the worktree is left clean (merge aborted) (green)
- [X] T013 [US4] Per-branch failure isolation — **not duplicated here** (branch now based on **stable**). This is a component-level concern owned by `backend/tests/component/git/test_git_repository.py::test_sync_continues_after_branch_pull_failure`, which exists on **develop** (commit `53933dbdb`) but **not** in the current stable base. On stable the guarantee is a known gap, already fixed + tested upstream; it lands in stable when develop merges. Replicating it at the integration/Gogs level would duplicate develop's component test, so it is intentionally out of scope for this suite.

**Checkpoint**: conflict/divergence behaviour characterised; two defects reproduced as `xfail`.

---

## Phase 6: User Story 5 — Filter does not isolate fetch-time failures (Priority: P3)

**Goal**: Determine whether a fetch-time problem on an excluded ref breaks in-filter branches.

**Independent Test**: run the file; the green filter test passes; the blast-radius test `xfails`.

- [X] T014 [US5] `test_filter_excludes_branch` — a branch outside `INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` (set **before** registration) is not imported as a standalone branch (green). Verified on stable.
- [X] T015 [US5] Fetch-trigger spike — **resolved: no reproducing trigger via force-push.** `fetch()` uses `prune=True, tags=True, prune_tags=True`, so a rewritten/force-pushed excluded ref force-updates without error. Suspected defect (b) (fetch-before-filter blast radius) is **refuted** in practice; no failing check added.
- [X] T016 [US5] `test_fetch_tolerates_problematic_excluded_ref` — a force-pushed (rewritten) branch outside the filter does **not** break in-filter syncing; the in-filter default branch still imports. Green guard documenting that the fetch-before-filter blast radius is not reachable via force-push (suspected defect (b) refuted). Verified on stable.

### Extra write-back robustness angles (added mid-implementation, approved by user)

Beyond the happy path, in the same file — all verified on stable:

- [X] A1 Permanence — a dropped write-back is not re-delivered by a later sync (`xfail`).
- [X] A2 Post-drop convergence — the repo does **not** converge; `merge()` records the commit before
  the push is confirmed, so a dropped push leaves the graph diverged and stuck (`xfail`). Pure
  divergence recovers; write-back-drop divergence does not. **New finding** — folded into the non-ff
  issue draft with a two-part fix.
- [X] A3 Repeated non-ff write-backs are each dropped (`xfail`).
- [X] A4 Drop is independent of `USE_EXPLICIT_MERGE_COMMIT` (`xfail`).
- [X] A5 `GIT_CONFIG_GLOBAL` `pull.rebase=true` lever does **not** rescue the stuck state (`xfail`) —
  confirms the fix must be in code, not a git-config workaround.

**Checkpoint**: deterministic prong complete — 13 tests (6 green guards, 7 `xfail`), one file, CI-resident.

---

## Phase 7: User Story 2 — Read-only consumer isolation & promotion (Priority: P1, full-stack)

**Goal**: Faithful two-instance Approach-A demonstration (opt-in, not CI-gated).

**Independent Test**: run the opt-in suite; all four US2 tests pass across two live stacks.

**⚠️ Sequenced last despite P1**: needs the novel two-stack harness and is opt-in/non-CI; the
deterministic prong is the CI-resident MVP.

- [ ] T017 [US2] Implement the two-instance harness in `backend/tests/integration_docker/test_multi_env_approach_a.py`: boot a development stack and a read-only consumer stack that **bind-mount the same host remote dir**; verify two stacks share one remote (resolves research open-verification: two-stack shared remote)
- [ ] T018 [US2] Add `test_consumer_imports_only_its_branch`: register the read-only consumer pinned to its branch on the shared remote, assert its `branch.all()` == {primary} only (green)
- [ ] T019 [US2] Add `test_isolation_dev_advance_invisible_to_consumer`: advance the development instance's branch on the shared remote, assert the consumer's recorded `commit` is unchanged (green)
- [ ] T020 [US2] Add `test_promotion_invisible_before_reimport`: promote a change onto the consumer's branch on the shared remote without reimport, assert the consumer's `commit` equals the pre-promotion SHA (green)
- [ ] T021 [US2] Add `test_reimport_advances_consumer`: call `InfrahubReadOnlyRepositoryImportLastCommit` and poll, assert the consumer's `commit` advances to the promoted SHA (green)

**Checkpoint**: full Approach-A pattern demonstrated end-to-end across two instances.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T022 [P] One consolidated draft for review: `issue-drafts/9568-comment.md`. The non-ff drop is **folded into #9568** (same root cause), not a separate issue. The comment covers the deterministic repro, the non-ff trigger, and the compounding permanent-divergence finding, with a two-part fix. Post **after** the PR lands (fill in PR #). Not submitted, per the issue-drafting workflow. (per the recorded issue-drafting workflow). T010 and T016 were **refuted** (green guards) — no issue.
- [X] T023 [P] Grepped the test file: no issue IDs, no `sync_status`, no sleeps; every `xfail` reason is behaviour-named (code-doc-style gate passes).
- [X] T024 `ruff check` + `ruff format` clean on `test_multi_env_writeback.py` (fixed a `== ""` comparison and reformatting).
- [~] T025 Deterministic prong ran consistently across ~6 development runs (2 xfailed, 6 passed each), well within `timeout = 300`. A dedicated 3× flake run + full-stack CI-exclusion check remain deferred until US2 / CI wiring lands.
- [ ] T026 [P] Run `specs/001-multi-env-repo-tests/quickstart.md` end-to-end and correct any drift

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → no deps.
- **Foundational (T003–T005)** → after Setup; blocks US1/US3/US4/US5.
- **US1 (T006–T007)** → after Foundational. **MVP.**
- **US3 (T008–T009)**, **US4 (T010–T013)**, **US5 (T014–T016)** → after Foundational; same file as US1 so **sequential** (append tests to the one module in this order).
- **US2 (T017–T021)** → after Setup (T002); independent file + harness; T017 blocks T018–T021.
- **Polish (T022–T026)** → after the stories whose defects/behaviour they cover.

### Within the deterministic prong

- T003 before any test that pushes a write-back (T006, T011).
- T004/T005 helpers before the tests that use them.
- Green guards (T008, T009, T012, T013, T014) may be authored in any order but land in the same file, so commit sequentially.

---

## Parallel Opportunities

- T002 `[P]` with T001 (different files).
- T004, T005 `[P]` with each other (independent helpers) but both land in the deterministic module — coordinate the single-file edits.
- **US2 (Phase 7) can be developed in parallel with the deterministic prong** by a second person: different file (`test_multi_env_approach_a.py`), different harness. Only Setup/Foundational are shared.
- T022 issue drafts are `[P]` per defect; T023 and T026 are `[P]`.

---

## Implementation Strategy

### MVP first (US1 only)

1. Setup (T001) + Foundational (T003–T005).
2. US1 (T006–T007) → the #9568 deterministic reproduction, `xfailed`, CI-resident.
3. **Stop & validate**: zero flake across repeated runs.

### Incremental delivery

1. MVP (US1) → the headline defect signal.
2. US3 → non-main default regression guard (green).
3. US4 → conflict/divergence characterisation (2 green + 2 `xfail`).
4. US5 → filter blast-radius (1 green + 1 `xfail`, after the trigger spike).
5. US2 → the full two-instance demonstration (opt-in).
6. Polish → draft issues for confirmed defects (for review), lint, flake check.

### Notes

- Verify each `xfail(strict)` test *fails as predicted* (xfailed) before moving on; an unexpected
  `XPASS` means the defect wasn't reproduced (or was fixed) — investigate, don't ignore.
- Green guards should pass immediately; a red green-guard is a real regression to chase.
- Commit after each logical group; keep the deterministic prong (one file) commits sequential.
