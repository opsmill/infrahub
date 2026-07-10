---
description: "Task list for IFC-2704 incremental merge regeneration"
---

# Tasks: Incremental generator & artifact execution on merge

**Input**: Design documents in `specs/ifc-2704-incremental-merge-regen/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md)
(D1–D9, D4a), [data-model.md](./data-model.md), [contracts/](./contracts/),
[quickstart.md](./quickstart.md), [critiques/](./critiques/)

**Tests**: Included — mandated by Constitution IV (Test Discipline) and the spec's Testing
Focus. This is a triggered-action path, so integration Docker coverage is required.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 = selective regeneration; US2 = repo-code changes; US3 = safe fallback;
  US4 = reversible rollout
- Exact file paths are backend-relative (repo root `backend/infrahub/…`, tests `backend/tests/…`)

## Story independence note

Unlike a typical feature, US1–US4 share one selection routine and one capture path. The
**Foundational** phase carries the capture/cache/threading/refactor that every story needs;
**US1** builds the selection routine; **US2/US3/US4** extend and harden it. US3 (safe fallback)
is P1 alongside US1 because the no-under-execution invariant is a correctness guarantee, not a
nice-to-have. Deliverable order is Foundational → US1 → US3 → US2 → US4 → cascade → polish.

---

## Phase 1: Setup

**Purpose**: config flag, generated files, and the one blocking design decision.

- [ ] T001 Add `selective_execution_after_merge: bool = True` to `MainSettings` in `backend/infrahub/config.py` (mirror `delete_branch_after_merge`, description + env `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`)
- [ ] T002 Regenerate generated config files and confirm the CI validators pass locally: `uv run invoke release.gen-config-env --update-docker-file` (updates `docker-compose.yml`) and `uv run invoke docs.generate` (updates `docs/docs/reference/configuration.mdx`); verify `uv run invoke release.validate-dockercomposeenv` and `uv run invoke docs.validate`
- [ ] T003 **Blocking spike (D7/E4)** — determine whether the existing event-driven machinery regenerates artifacts on generator-produced data mutations after a direct merge; record the outcome in `research.md` (Decision 7): either "events cover it → drop the fallback" or "not covered → sequence full artifact regen after generator completion". This decision gates T035.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No story work begins until this phase is complete. This is the diff-capture,
cache, threading, and shared-primitive refactor from D1–D5.

- [ ] T004 [P] Implement `EnrichedDiffNode → NodeDiff` converter in NEW `backend/infrahub/core/merge/diff_summary.py` per [contracts/merge-diff-summary.md](./contracts/merge-diff-summary.md): uppercase action names, **default/target branch** tag, `attributes`+`relationships` → `elements[]` (element_type from cardinality, peers from relationship members), retain conflict-resolved-to-base nodes, exclude `UNCHANGED`
- [ ] T005 [P] Implement `set_merge_diff_summary_cache` / `get_merge_diff_summary_cache` in `backend/infrahub/core/merge/diff_summary.py` (key `branch_merge:diff_id:{diff_root_uuid}`, `list[NodeDiff]` JSON, `KVTTL.TWO_HOURS`); getter raises `ResourceNotFoundError` on miss
- [ ] T006 Capture in `BranchMergeOrchestrator.merge` (`backend/infrahub/core/merge/orchestrator.py`), split around the point of no return: (a) serialize the already-loaded in-memory `branch_diff` into `list[NodeDiff]` before `freeze_diffs_for_branch` (:151); (b) call `set_merge_diff_summary_cache` **only after** the `BranchStatus.MERGED` transition (:155-157) and write-block lift (:161), immediately before `run_follow_ups` (:163), yielding `merge_diff_cache_key = diff_root_uuid`. Wrap both (a) and (b) in their own try/except → `None` on failure, never re-raise (critique E7). A rolled-back merge writes nothing. Depends on T004, T005
- [ ] T007 Thread `merge_diff_cache_key: str | None` through `PostMergeDispatcher.run_follow_ups` (`backend/infrahub/core/merge/post_merge.py`) into the `BRANCH_MERGE_POST_PROCESS` parameters dict (:100-104). Depends on T006
- [ ] T008 Add `merge_diff_cache_key: str | None = None` parameter to `post_process_branch_merge` (`backend/infrahub/core/branch/tasks.py:434`). Depends on T007
- [ ] T009 Generalize the selection primitives in `backend/infrahub/proposed_change/tasks.py` — the predicates (`_query_changed`, `_definition_changed`) and `get_field_level_impacted_subscribers` — to accept a **resolved `diff_summary: list[NodeDiff]`** and an **explicit query branch**; keep the PC callers passing their cached summary and source branch unchanged (D4, critique E3)
- [ ] T010 [P] Add `members: list[str] = Field(default_factory=list)` to `RequestArtifactDefinitionGenerate` (`backend/infrahub/git/models.py:19-28`) and consume it in `generate_request_artifact_definition` (`backend/infrahub/git/tasks.py:594-598`), filtering on `member.id` (mirror `target_members`); leave `limit` intact — per [contracts/artifact-generate-members.md](./contracts/artifact-generate-members.md)

### Foundational tests

- [ ] T011 [P] Unit test the converter in `backend/tests/unit/core/merge/test_diff_summary.py`: all element types, action uppercasing, conflict-to-base retained, relationship/membership changes, `UNCHANGED` excluded, default-branch tag
- [ ] T012 [P] Unit test the cache round-trip (set→get, miss raises) in `backend/tests/unit/core/merge/test_diff_summary.py`
- [ ] T013 [P] Unit test the `members` filter (limit trap) in `backend/tests/unit/git/`: a group with one existing-artifact member and one artifact-less new member — `members=[both ids]` → both processed; `members=[]` → all processed
- [ ] T014 [P] Regression test that the PC selection path is unchanged after the T009 refactor (existing PC tests pass; add one asserting a resolved-summary call equals the cached-summary call)

**Checkpoint**: the diff is captured and reachable in the follow-up; primitives accept a merge summary; the artifact member filter exists. Story work can begin.

---

## Phase 3: User Story 1 — Selective regeneration on merge (Priority: P1) 🎯 MVP

**Goal**: Only the definitions and members affected by the merge diff run. (FR-001, FR-009,
FR-010; SC-001, SC-002.)

**Independent Test**: Merge a branch changing one object of one kind → only definitions whose
`query_models` include that kind dispatch, only for the affected member(s).

- [ ] T015 [US1] Implement definition-level selection in NEW `backend/infrahub/core/merge/selective_regen.py`: build `RegenerationDefinition`-satisfying models for artifact + generator definitions on the target branch; apply gates `_query_changed`, `_definition_changed` (incl. fingerprint element), `MODIFIED_KINDS` ∩ `query_models` (artifact Profile-strip variant), the `execute_after_merge` generator filter, and the **group-membership gate** (select when the definition's target group appears in the summary). Depends on T009
- [ ] T016 [US1] Implement member-level reconciliation in `selective_regen.py` per [contracts/branch-merge-post-process.md](./contracts/branch-merge-post-process.md) and data-model §5: fetch live group members on the **target branch**, build `member.id → subscriber_id`, compute `managed_branch`, run `get_field_level_impacted_subscribers` (query_branch=target), decide `render(member)` (managed_branch | no-subscriber new member | scope ALL | subscriber ∈ impacted ids), emit **member-id** `target_members` / `members` filters. Depends on T015, T010
- [ ] T017 [US1] Wire the selective path into `post_process_branch_merge` (`branch/tasks.py`): when `config.SETTINGS.main.selective_execution_after_merge` and `merge_diff_cache_key` present and summary loads → call `selective_regen` and dispatch `REQUEST_GENERATOR_DEFINITION_RUN` / `REQUEST_ARTIFACT_DEFINITION_GENERATE`. Depends on T016, T008

### Tests for User Story 1

- [ ] T018 [P] [US1] Functional: single-kind change dispatches only matching definitions, only for the affected member (quickstart #1) in `backend/tests/functional/`
- [ ] T019 [P] [US1] Functional: SPECIFIC-scope field change — impacted subscriber ids correctly mapped to member ids; no member wrongly dropped (quickstart #16, critique E1)
- [ ] T020 [P] [US1] Functional: new object created and added to a targeted group regenerates for the new member (quickstart #3, FR-007)
- [ ] T021 [P] [US1] Functional: existing object added to a targeted group (membership-only) is selected via the group-membership gate and regenerates (quickstart #15, critique E2)
- [ ] T022 [P] [US1] Functional: a merge changing nothing any definition reads dispatches nothing (quickstart #2)

**Checkpoint**: selective regeneration works end-to-end for data and membership changes with correct member scoping.

---

## Phase 4: User Story 3 — Safe fallback to full regeneration (Priority: P1)

**Goal**: Every uncertain path regenerates everything rather than risk a stale artifact.
(FR-008, FR-010; SC-003.)

**Independent Test**: Force each fallback condition and confirm full regeneration with nothing
left stale.

- [ ] T023 [US3] Fallback wiring in `post_process_branch_merge`: flag off / `merge_diff_cache_key is None` / `get_merge_diff_summary_cache` raises `ResourceNotFoundError` → submit the two `TRIGGER_*` workflows exactly as today (byte-for-byte current behavior). Depends on T017
- [ ] T024 [US3] In `selective_regen.py`: null-`fingerprint` + repository code signal in the diff → select **all** definitions of that repository; `dependencies` null or `dependencies_complete != True` → select the definition (over-execution). Depends on T015
- [ ] T025 [US3] Resolve E6: verify a source-branch code change yields a `CoreRepository`/`CoreGenericRepository` node with a triggering `commit` element in `branch_diff.nodes` at capture; if present use it, else escalate any null-fingerprint definition to repository-wide full regeneration. Update research.md D6 with the finding. Depends on T024

### Tests for User Story 3

- [ ] T026 [P] [US3] Functional: cache entry forced absent → full regeneration (quickstart #8)
- [ ] T027 [P] [US3] Functional: null fingerprint + repo commit change → all repo definitions regenerate (quickstart #9)
- [ ] T028 [P] [US3] Functional: `dependencies_complete != True` → definition regenerates (quickstart #10)

**Checkpoint**: no fallback path can under-execute.

---

## Phase 5: User Story 2 — Repository code changes still regenerate (Priority: P2)

**Goal**: Code changes regenerate affected definitions via the fingerprint-in-diff signal;
net-zero edits regenerate nothing. (FR-004, FR-005, FR-006; SC-005.)

**Independent Test**: Merge a transform-file change → affected definitions regenerate; merge an
edit-then-revert → nothing regenerates.

- [ ] T029 [US2] Confirm/finish the fingerprint-in-diff path in `selective_regen.py`: a definition whose `fingerprint` attribute changed is selected by `_definition_changed` (no special casing); add explicit logging of the repo-code selection reason. Depends on T015

### Tests for User Story 2

- [ ] T030 [P] [US2] Functional: transform-file change on the branch regenerates the affected definitions (quickstart #5)
- [ ] T031 [P] [US2] Functional: edit-then-revert of a transform file dispatches zero regeneration (quickstart #6, SC-005)
- [ ] T032 [P] [US2] Functional: a query/definition edited over the API (no import) still regenerates dependent definitions (quickstart #7)

**Checkpoint**: repo-code and API-edit change detection is correct in both directions.

---

## Phase 6: User Story 4 — Reversible rollout via configuration (Priority: P3)

**Goal**: The flag disables selective behavior, restoring the prior full-regeneration baseline.
(FR-012; SC-004.)

- [ ] T033 [US4] Confirm the flag-off branch in `post_process_branch_merge` reproduces the prior blanket path (covered by T023; add the explicit assertion). Depends on T023

### Tests for User Story 4

- [ ] T034 [P] [US4] Functional: flag on → selective path; flag off → full fan-out (quickstart #14 behavior half)

---

## Phase 7: Direct-merge generator cascade (D7)

**Goal**: Artifacts consuming generator output are not left stale on direct merges. (FR-011.)
Depends on the T003 spike outcome.

- [ ] T035 Implement the T003 outcome in `post_process_branch_merge` / `selective_regen.py`: if events cover generator→artifact staleness, rely on them (no extra submission); else, on a direct (non-PC) merge with ≥1 generator dispatched, submit full artifact regeneration **sequenced after** generator completion (awaited), never concurrent (critique E4). Depends on T003, T017
- [ ] T036 [P] Functional: direct-merge with an `execute_after_merge` generator → artifacts consuming its output are regenerated (not stale) (quickstart #11, FR-011)

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T037 Observability (E8): emit a per-merge log/metric recording the selective-vs-fallback path and dispatched generator/artifact counts, in `post_process_branch_merge`
- [ ] T038 No-double-trigger regression (D8): a transform-file-change merge triggers regeneration exactly once despite the default-branch re-import (quickstart #12)
- [ ] T039 Integration Docker test in `backend/tests/integration_docker/`: full testing-focus matrix (single-kind, new target, conflict-to-base, repo-code change, fallbacks) on the live stack
- [ ] T040 Baseline scale test (SC-004): record dispatched-task count before/after with the flag on vs off on a representative dataset (quickstart #14 scale half)
- [ ] T041 [P] Run `quickstart.md` end to end and check off each scenario
- [ ] T042 [P] Add a towncrier changelog fragment under `changelog/` (performance/bugfix, referencing IFC-2704 / IFC-2306)
- [ ] T043 Run `/pre-ci` (format, ruff, ty, unit tests, generated-file + generated-doc validation) and fix any drift before pushing

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: T001–T002 independent; T003 is a decision gate for T035.
- **Foundational (P2)**: T004/T005 [P] → T006 → T007 → T008; T009 [P] and T010 [P] independent; tests T011–T014 after their targets. Blocks all stories.
- **US1 (P3-phase)**: after Foundational. T015 → T016 → T017.
- **US3 (P4-phase)**: T023 after T017; T024/T025 after T015. (P1 priority — do right after US1.)
- **US2 (P5-phase)**: T029 after T015.
- **US4 (P6-phase)**: T033 after T023.
- **Cascade (P7)**: T035 after T003 + T017.
- **Polish (P8)**: after the stories it covers.

### Parallel opportunities

- T004 ∥ T005 (same new file, coordinate) ; T009 ∥ T010 (different modules).
- All foundational tests T011–T014 in parallel once their targets land.
- Within each story, the `[P]` functional tests run in parallel.
- US2, US3, US4 test phases are independent of each other once US1's selection routine exists.

---

## Implementation Strategy

### MVP (correctness-complete)

The true MVP is **Foundational + US1 + US3**: selective regeneration *with* the safe fallback.
US1 alone is not shippable — without US3's fallbacks it can under-execute, violating the core
invariant. Ship these together, validate the no-under-execution matrix, then add US2/US4/cascade.

### Increments

1. Foundational → capture + primitives ready (not user-visible).
2. + US1 → selective dispatch (behind the flag, but unsafe alone).
3. + US3 → fallbacks close the under-execution holes → **safe to enable**.
4. + US2 → repo-code correctness hardened.
5. + US4 → rollout/baseline switch validated.
6. + Cascade (T035) → direct-merge generator output covered.
7. + Polish → observability, scale baseline, integration matrix, changelog, pre-ci.

## Notes

- [P] = different files, no incomplete dependency.
- Commit after each task or logical group; run `/pre-ci` before pushing (T043).
- The load-bearing safety step is T016 (member reconciliation) + T024 (fallbacks); give them
  the most test attention.
- No core-schema, GraphQL-schema, or new-dependency changes — if any task appears to need one,
  stop and re-check the design (it should not).
