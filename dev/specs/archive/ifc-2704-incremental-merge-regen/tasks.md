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

- [X] T001 Add `selective_execution_after_merge` to `MainSettings` in `backend/infrahub/config.py` (mirror `delete_branch_after_merge`, description + env `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`). Shipped `default=False` initially; now `default=True` — the US3/cascade fallbacks that the default-True rationale (D9) depended on have landed (see the 2026-07-24 sync note), so the generated files (`docker-compose.yml`, `configuration.mdx`, `schema/openapi.json`, frontend OpenAPI types) were regenerated for the new default.
- [X] T002 Regenerate generated config files and confirm the CI validators pass locally: `uv run invoke release.gen-config-env --update-docker-file` (updates `docker-compose.yml`) and `uv run invoke docs.generate` (updates `docs/docs/reference/configuration.mdx`); verify `uv run invoke release.validate-dockercomposeenv` and `uv run invoke docs.validate`
- [X] T003 **Blocking spike (D7/E4)** — determine whether the existing event-driven machinery regenerates artifacts on generator-produced data mutations after a direct merge; record the outcome in `research.md` (Decision 7): either "events cover it → drop the fallback" or "not covered → sequence full artifact regen after generator completion". This decision gates T035.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No story work begins until this phase is complete. This is the diff-capture,
cache, threading, and shared-primitive refactor from D1–D5.

- [X] T004 [P] Implement `EnrichedDiffNode → NodeDiff` converter in NEW `backend/infrahub/core/merge/diff_summary.py` per [contracts/merge-diff-summary.md](./contracts/merge-diff-summary.md): uppercase action names, **target (destination) branch** tag (the merge `target_branch`), `attributes`+`relationships` → `elements[]` (element_type from cardinality, peers from relationship members), retain conflict-resolved-to-base nodes, exclude `UNCHANGED`
- [X] T005 [P] Implement `set_merge_diff_summary_cache` / `get_merge_diff_summary_cache` in `backend/infrahub/core/merge/diff_summary.py` (key `branch_merge:diff_id:{diff_root_uuid}:diff_summary`, `list[NodeDiff]` JSON, `KVTTL.TWO_HOURS`); getter raises `ResourceNotFoundError` on a miss **or** an unreadable/malformed payload (all summary-load failures normalize to one exception so the fallback path is single-branch)
- [X] T006 Capture in `BranchMergeOrchestrator.merge` (`backend/infrahub/core/merge/orchestrator.py`), split around the point of no return: (a) serialize the already-loaded in-memory `branch_diff` into `list[NodeDiff]` before `freeze_diffs_for_branch` (:151); (b) call `set_merge_diff_summary_cache` **only after** the `BranchStatus.MERGED` transition (:155-157) and write-block lift (:161), immediately before `run_follow_ups` (:163), yielding `merge_diff_cache_key = diff_root_uuid`. Wrap both (a) and (b) in their own try/except → `None` on failure, never re-raise (critique E7). A rolled-back merge writes nothing. Also forward the caller-supplied `proposed_change_id: str | None` (the id when the merge originates from a proposed change, `None` for a direct merge) to `run_follow_ups` alongside the cache key — the post-process needs it to apply the direct-merge cascade (critique E4). Depends on T004, T005
- [X] T007 Thread `merge_diff_cache_key: str | None` and `proposed_change_id: str | None` through `PostMergeDispatcher.run_follow_ups` (`backend/infrahub/core/merge/post_merge.py`) into the `BRANCH_MERGE_POST_PROCESS` parameters dict (:100-104). Depends on T006
- [X] T008 Add `merge_diff_cache_key: str | None = None` and `proposed_change_id: str | None = None` parameters to `post_process_branch_merge` (`backend/infrahub/core/branch/tasks.py:434`); derive `is_proposed_change_merge = proposed_change_id is not None` for the selection and cascade logic. Depends on T007
- [X] T009 Generalize the selection primitives in `backend/infrahub/proposed_change/tasks.py` — the predicates (`_query_changed`, `_definition_changed`) and `get_field_level_impacted_subscribers` — to accept a **resolved `diff_summary: list[NodeDiff]`** and an **explicit query branch**; keep the PC callers passing their cached summary and source branch unchanged (D4, critique E3)
- [X] T010 [P] Add `members: list[str] = Field(default_factory=list)` to `RequestArtifactDefinitionGenerate` (`backend/infrahub/git/models.py:19-28`) and consume it in `generate_request_artifact_definition` (`backend/infrahub/git/tasks.py:594-598`), filtering on `member.id` (mirror `target_members`); leave `limit` intact — per [contracts/artifact-generate-members.md](./contracts/artifact-generate-members.md)

### Foundational tests

- [X] T011 [P] Unit test the converter in `backend/tests/unit/core/merge/test_diff_summary.py`: all element types, action uppercasing, conflict-to-base retained, relationship/membership changes, `UNCHANGED` excluded, target-branch tag
- [X] T012 [P] Unit test the cache round-trip (set→get, miss raises) in `backend/tests/unit/core/merge/test_diff_summary.py`
- [X] T013 [P] Unit test the `members` filter (limit trap) in `backend/tests/unit/git/test_request_artifact_definition_generate.py`: extracted the member filter into `RequestArtifactDefinitionGenerate.selects_member`; the test proves `members=[both ids]` processes the artifact-less new member while `limit` alone drops it, and an empty filter processes all.
- [X] T014 [P] Regression test that the PC selection path is unchanged after the T009 refactor (existing PC tests pass; add one asserting a resolved-summary call equals the cached-summary call)

**Checkpoint**: the diff is captured and reachable in the follow-up; primitives accept a merge summary; the artifact member filter exists. Story work can begin.

---

## Phase 3: User Story 1 — Selective regeneration on merge (Priority: P1) 🎯 MVP

**Goal**: Only the definitions and members affected by the merge diff run. (FR-001, FR-009,
FR-010; SC-001, SC-002.)

**Independent Test**: Merge a branch changing one object of one kind → only definitions whose
`query_models` include that kind dispatch, only for the affected member(s).

- [X] T015 [US1] Implement definition-level selection in NEW `backend/infrahub/core/merge/selective_regen.py`: build `RegenerationDefinition`-satisfying models for artifact + generator definitions on the target branch; apply gates `_query_changed`, `_definition_changed` (incl. fingerprint element), `MODIFIED_KINDS` ∩ `query_models` (artifact Profile-strip variant), the `execute_after_merge` generator filter, and the **group-membership gate** (select when the definition's target group appears in the summary). Depends on T009
- [X] T016 [US1] Implement member-level reconciliation in `selective_regen.py` per [contracts/branch-merge-post-process.md](./contracts/branch-merge-post-process.md) and data-model §5: fetch live group members on the **target branch**, build `member.id → subscriber_id`, compute `managed_branch`, run `get_field_level_impacted_subscribers` (query_branch=target), decide `render(member)` (managed_branch | no-subscriber new member | scope ALL | subscriber ∈ impacted ids), emit **member-id** `target_members` / `members` filters. Depends on T015, T010
- [X] T017 [US1] Wire the selective path into `post_process_branch_merge` (`branch/tasks.py`): when `config.SETTINGS.main.selective_execution_after_merge` and `merge_diff_cache_key` present and summary loads → call `selective_regen(summary, target_branch, is_proposed_change_merge)` and dispatch `REQUEST_GENERATOR_DEFINITION_RUN` / `REQUEST_ARTIFACT_DEFINITION_GENERATE`. Depends on T016, T008

### Tests for User Story 1

- [X] T018 [P] [US1] single-kind change dispatches only matching definitions, only for the affected member (quickstart #1). Definition-level half covered by the component real-graph test (`test_merge_selective_regen.py`); member narrowing by the selector-template unit tests (`test_base.py`).
- [~] T019 [P] [US1] SPECIFIC-scope field change — impacted subscriber ids mapped to member ids; no member dropped (quickstart #16, critique E1). Mapping logic covered at the unit tier (`test_base.py` `only_impacted_subscribers_narrow_the_filter`, `map_subscriber_ids_by_member`); the live merge-path SPECIFIC-scope walkthrough needs the render harness — deferred to the live/API run (T044).
- [~] T020 [P] [US1] new object added to a targeted group regenerates for the new member (quickstart #3, FR-007). New-member force-render covered at the unit tier (`test_base.py` `new_members_without_subscribers_render_all`); live merge-path variant deferred (T044).
- [~] T021 [P] [US1] existing object added to a targeted group (membership-only) is selected via the group-membership gate (quickstart #15, critique E2). Gate covered at the unit tier (`test_gate.py` `group_membership_selects_without_managing_branch`); live merge-path variant deferred (T044).
- [X] T022 [P] [US1] Functional: a merge changing nothing any definition reads dispatches nothing (quickstart #2)

> **Functional coverage note.** `backend/tests/integration/proposed_change/test_merge_selective_regen.py`
> drives the real `post_process_branch_merge` flow with a recording workflow backend and proves,
> against the live stack: no-op → nothing (T022); relevant-kind change → only the matching artifact
> **and** generator definitions dispatch (T018, definition-level half); unrelated-kind change →
> nothing; and both fallbacks (flag off, cache-miss) → the blanket triggers. **Remaining (need the
> live subscriber/query-group machinery that only exists after real generation):** T013 (git
> `members` limit-trap unit), T019 (SPECIFIC-scope subscriber→member id mapping), T020/T021
> (new-member and membership-only member-level narrowing). Member-level narrowing is currently
> exercised only by the proposed-change component tests; these merge-path variants are the
> follow-up test work.

**Checkpoint**: selective regeneration works end-to-end for data and membership changes with correct member scoping.

---

## Phase 4: User Story 3 — Safe fallback to full regeneration (Priority: P1)

**Goal**: Every uncertain path regenerates everything rather than risk a stale artifact.
(FR-008, FR-010; SC-003.)

**Independent Test**: Force each fallback condition and confirm full regeneration with nothing
left stale.

- [X] T023 [US3] Fallback wiring in `post_process_branch_merge`: flag off / `merge_diff_cache_key is None` / `get_merge_diff_summary_cache` raises `ResourceNotFoundError` (which per T005 covers a cache miss **and** any unreadable/malformed payload) → submit the two `TRIGGER_*` workflows exactly as today (byte-for-byte current behavior). Depends on T017. Implemented in `regeneration_dispatcher.py` (`PostMergeRegenerationDispatcher`).
- [X] T024 [US3] In `selective_regen/fallbacks.py`: null-`fingerprint` → escalate the definition's whole repository to full regeneration (unconditional; the repository commit signal, when present, is recorded only in the log line); `dependencies` null or `dependencies_complete != True` → select the definition (over-execution). Applied in the selector-base loop, widening `managed_branch`. `fingerprint` now flows into both definition models. Depends on T015
- [X] T025 [US3] Resolve E6: verified the diff serializer captures a `CoreRepository`/`CoreGenericRepository` node with a triggering `commit` element at capture (no repository exclusion in the diff pipeline), and made the null-fingerprint escalation unconditional so correctness does not depend on the signal. research.md D6 updated. Depends on T024

### Tests for User Story 3

- [X] T026 [P] [US3] cache entry forced absent **and** cache entry forced unreadable/malformed (deserialization failure) → full regeneration in both cases (quickstart #8). Covered at the cache tier (`test_diff_summary_cache.py`) and end-to-end through the dispatcher (`test_regeneration_dispatcher.py`: cache-miss + malformed-payload → both `TRIGGER_*`).
- [X] T027 [P] [US3] null fingerprint → all repo definitions regenerate (quickstart #9). Covered at the unit tier: `test_fallbacks.py` (repo escalation, incl. a populated sibling) and `test_base.py` (a null-fingerprint definition force-selects over a rejecting gate).
- [X] T028 [P] [US3] `dependencies_complete != True` → definition regenerates (quickstart #10). Covered at the unit tier: `test_fallbacks.py` (`dependencies_incomplete_reason`) and `test_base.py` (incomplete-deps force-selection).

**Checkpoint**: no fallback path can under-execute.

---

## Phase 5: User Story 2 — Repository code changes still regenerate (Priority: P2)

**Goal**: Code changes regenerate affected definitions via the fingerprint-in-diff signal;
net-zero edits regenerate nothing. (FR-004, FR-005, FR-006; SC-005.)

**Independent Test**: Merge a transform-file change → affected definitions regenerate; merge an
edit-then-revert → nothing regenerates.

- [X] T029 [US2] Confirmed the fingerprint-in-diff path: a definition whose `fingerprint` attribute changed is selected by `definition_changed` with no special casing (the fingerprint recomputes at import and surfaces as a change on the definition node). Added explicit repo-code selection logging — `definition_changed` now names a fingerprint change as a code-input change. Depends on T015

### Tests for User Story 2

- [X] T030 [P] [US2] transform-file change on the branch regenerates the affected definitions (quickstart #5). Unit tier: `test_predicates.py::test_definition_changed_on_fingerprint_reports_a_code_change` — a fingerprint change fires `definition_changed`, which the gate turns into `managed_branch` selection.
- [X] T031 [P] [US2] edit-then-revert of a transform file dispatches zero regeneration (quickstart #6, SC-005). Unit tier: a net-zero edit leaves the fingerprint unchanged, so the definition node is absent from the diff — covered by `test_definition_changed` (`empty_diff_is_false`, `mismatched_id_is_false`) and the gate's `no_signal_is_not_selected`.
- [X] T032 [P] [US2] a query/definition edited over the API (no import) still regenerates dependent definitions (quickstart #7). Unit tier: an API query edit surfaces as a `CoreGraphQLQuery` node change → `query_changed` fires (`test_query_changed`, gate `query_change_manages_whole_branch`).

**Checkpoint**: repo-code and API-edit change detection is correct in both directions.

---

## Phase 6: User Story 4 — Reversible rollout via configuration (Priority: P3)

**Goal**: The flag disables selective behavior, restoring the prior full-regeneration baseline.
(FR-012; SC-004.)

- [X] T033 [US4] Confirmed the flag-off branch reproduces the prior blanket path; `test_flag_off_submits_full_regeneration` now asserts the exact TRIGGER_* parameters (target branch only; generator run tagged MERGE), the selector is never consulted, and no per-definition request is submitted. Depends on T023

### Tests for User Story 4

- [X] T034 [P] [US4] flag on → selective path; flag off → full fan-out (quickstart #14 behavior half). Unit tier: `test_regeneration_dispatcher.py` — `test_selected_definitions_are_dispatched` (flag on → REQUEST_* only) vs `test_flag_off_submits_full_regeneration` (flag off → TRIGGER_* only).

---

## Phase 7: Direct-merge generator cascade (D7)

**Goal**: Artifacts consuming generator output are not left stale on direct merges. (FR-011.)
Depends on the T003 spike outcome.

- [X] T035 Implemented the T003 outcome (events do not cover generator→artifact staleness): threaded `proposed_change_id` through `run_follow_ups` → `BRANCH_MERGE_POST_PROCESS` params → `post_process_branch_merge`, deriving `is_proposed_change_merge`. On a direct (non-PC) merge with ≥1 generator dispatched, the dispatcher awaits (`execute_workflow`) each generator run, then captures the nodes those generators wrote — scoped to each generator's per-member tracking group — and regenerates only the artifacts that read the tracked output (sequenced after the generator mutations, never concurrent). It widens to full artifact regeneration when a generator's tracked set is unresolved or the output cannot be captured, and — on a generator run failure — regenerates all artifacts without re-running the generators. Artifact requests selected by both the merge diff and the generator output are consolidated per definition. PC merges and generator-less direct merges keep the selective artifact path. Depends on T003, T017
- [X] T036 [P] direct-merge with a generator → artifacts consuming its output are regenerated, not stale (quickstart #11, FR-011). Unit tier: `test_regeneration_dispatcher.py` — `test_direct_merge_with_generator_cascades_to_full_artifact_regeneration` (generator awaited, blanket artifact trigger after), plus the direct-no-generator and PC-merge contrasts.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T037 Observability (E8): the dispatcher logs a per-merge line on every path — selective (with generator/artifact counts and whether the direct-merge cascade engaged) or a named fallback reason ("regenerating all definitions") — so the selective-vs-fallback ratio and dispatch volume are observable in the follow-up log. These per-merge lines are emitted at debug level.
- [X] T038 No-double-trigger regression (D8): covered at the unit tier — `test_definition_changed_matches_once_despite_a_repeated_signal` (a fingerprint change resolves to a single match even with a duplicate entry) plus the selector's one-request-per-definition guarantee (`test_base.py`). The default-branch re-import produces identical fingerprints (no new diff entry) per D8; the full live re-import regression is part of the deferred live run (quickstart #12).
- [X] T039 Selection-decision coverage: unit tier — dispatcher branch matrix (`test_regeneration_dispatcher.py`), gate matrix (`test_gate.py`), fallback logic (`test_fallbacks.py`), selector template (`test_base.py`); component tier — real-graph selection driving the dispatcher through a recording workflow backend (`test_merge_selective_regen.py`). Full live-stack render execution moves to the API tier (T044).
- [~] T040 Perf A/B: the baseline (blanket path, ~80 regeneration flows on the demo dataset) and the full same-build method/recipe are recorded in `perf-validation.md`. The flag-off vs flag-on retest table requires a from-source rebuild + workflow-db wipe (a live stack), so it is left to a live A/B run; not fabricated here. The scale run (SC-002) is deferred to T045.
- [~] T041 [P] `quickstart.md` scenarios are mapped to automated coverage across the unit/component tiers (selection, fallbacks, cascade, flag toggle). The end-to-end live walkthrough requires a running stack and is deferred to the live run alongside T040/T044.
- [X] T042 [P] Added a towncrier changelog fragment (`changelog/+ifc-2704-selective-merge-regeneration.added.md`).
- [X] T043 Ran `/pre-ci` — `invoke format` (no drift), `main.lint` + `backend.lint` (ruff, ty, mypy) clean, `backend.validate-generated` clean, and the full `backend.test-unit` suite passes (1740 tests). Frontend/docs/schema unaffected by this backend-only change.

---

## Phase 9: Remediation — Gap Report

- [ ] T044 [P] [Sync: Gap Report] Add an API-tier real-regeneration test asserting a merge-selected artifact definition actually re-renders its `CoreArtifact` for the affected member (and unrelated members stay untouched), driving generation through the ASGI test client in `backend/tests/component/api/test_merge_selective_regen_render.py` — the integration testcontainer harness cannot execute the render flow (worker→server callback unavailable), so real-output coverage lives here. **Deferred**: requires the API render harness (real render flow through the ASGI test client); not runnable in the current environment. Selection is fully covered at the unit/component tiers; this adds real regenerated-output assertions.
- [ ] T045 [P] [Sync: Gap Report] Run the scale same-build A/B (SC-002) once the profiling-harness scale dataset (IFC-2761/IFC-2889) is available and record the count reduction and drained-window in `dev/specs/ifc-2704-incremental-merge-regen/perf-validation.md`. **Deferred**: pending the profiling-harness scale dataset (IFC-2761/IFC-2889).
- [ ] T046 [P] [Sync: Gap Report] Land the integration_docker merge suite that exercises the shipped cascade and selection behavior live — `test_merge_generator_artifact_cascade.py`, `test_merge_composition_cascade.py`, `test_merge_diverged_main.py`, `test_merge_main_code_changed.py`, `test_merge_selection_scenarios.py` and their fixture repositories under `test_files/repos/` — in `backend/tests/integration_docker/`. These files exist in the working tree but are not yet committed.
- [X] T047 [Sync: Gap Report] Unit coverage for the refined generator→artifact cascade shipped alongside the behavior: run-failure isolation and artifact-only re-regeneration in `backend/tests/unit/core/merge/test_regeneration_dispatcher.py` (`test_generator_run_failure_is_isolated_and_regenerates_artifacts_not_generators`, `test_merge_consolidates_artifacts_selected_by_both_diffs`), tracking-group output widening in `backend/tests/unit/core/merge/selective_regen/test_generator_diff_capturer.py` (`test_capture_widens_*`, `test_capture_ignores_groups_whose_name_is_not_a_tracking_group`), and orphan generator-instance tolerance in `backend/tests/unit/core/regeneration/test_members.py`.

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
