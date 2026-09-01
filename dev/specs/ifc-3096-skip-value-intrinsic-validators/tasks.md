---
description: "Task list for IFC-3096 — stop emitting value-intrinsic constraint validators on data-only diffs"
---

# Tasks: Stop emitting value-intrinsic constraint validators on data-only diffs

**Input**: Design documents from `dev/specs/ifc-3096-skip-value-intrinsic-validators/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [quickstart.md](./quickstart.md), [critique](./critiques/critique-20260831-173029.md)

**Tests**: Included. The spec requests them explicitly (FR-004, FR-005 verification notes, and the Testing Decisions section).

**Branch**: `skip-value-intrinsic-validators-ifc-3096`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact; sites within a file are named by symbol, never line number

## Phase ordering note — read before starting

The phases below **do not** run in spec order (US1 → US2 → US3). They run in dependency order: **US3 → US2 → US1**. This is deliberate, and the reason is the shape of the feature:

- **US1 is the deliverable** — it removes validation work. Everything else exists to make that removal safe and durable.
- **US3's pinning test must exist before the flip.** Written first against *current* values, the flip then shows up as a reviewable diff in the expected literal — which is exactly what User Story 3's acceptance scenario asks for. Written afterwards, it merely ratifies whatever was done.
- **US2's safety test must exist before the flip.** Written first, it passes against current behaviour and becomes a genuine regression guard. Written afterwards, it is a post-hoc rationalisation that has never been observed to fail.

US1 and US2 are both P1; the spec itself says US2 "shares P1 because shipping User Story 1 without it would be shipping an unverified integrity risk." US3 is P2 but is a prerequisite in practice. Reordering P1 stories among themselves by dependency is legitimate and is done here on purpose.

**Consequence for MVP framing**: this feature's stories are *not* independently shippable in the usual sense. US1 alone is a validation removal with no guard; US2 and US3 alone change nothing user-visible. The shippable unit is all three. This is stated plainly rather than forced into an MVP shape the feature does not have.

---

## Phase 1: Setup

**Purpose**: Confirm the working environment and capture the green baseline

- [ ] T001 Confirm dependencies are installed and the SDK import resolves: run `uv sync --all-groups`, then `uv run python -c "import infrahub_sdk"`. If it fails, run `uv sync --all-groups --reinstall-package infrahub-server`
- [ ] T002 Capture the pre-change baseline: run `uv run pytest backend/tests/component/core/constraint_validators/ backend/tests/unit/core/validators/ -q` and record the pass count. Every later phase compares against this number

**Checkpoint**: Baseline green and recorded

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the evidence the classification rests on

**⚠️ CRITICAL**: No checker may be flipped until this phase completes. Tracing can **remove families from the flip list** — the plan does not assume all eight survive.

- [ ] T003 [P] Trace the write-time enforcement point for **attribute kind**: find where a value is validated/coerced against its attribute kind on every write, starting from the attribute layer's value-setting path. Record the module and symbol in a scratch note for the knowledge page
- [ ] T004 [P] Trace the write-time enforcement point for **attribute optionality** (mandatory-ness): find where a null is rejected for a mandatory attribute on write. Record module and symbol
- [ ] T005 [P] Trace the write-time enforcement point for **attribute regex** (`regex` and `parameters.regex`). Record module and symbol
- [ ] T006 [P] Trace the write-time enforcement point for **attribute length bounds** (`min_length`, `max_length`, and the `parameters.*` variants). Record module and symbol
- [ ] T007 [P] Trace the write-time enforcement point for **attribute enum**. Record module and symbol
- [ ] T008 [P] Trace the write-time enforcement point for **attribute dropdown choices**. Record module and symbol
- [ ] T009 [P] Trace the write-time enforcement point for **attribute numeric bounds and excluded values** (`parameters.min_value`, `parameters.max_value`, `parameters.excluded_values`), and confirm the strict-schema-validation setting that gates `AttributeNumberChecker.supports` is the same one gating the write-time check. Record module and symbol
- [ ] T010 [P] Confirm the **relationship peer** argument holds in code: that the effective allowed peer set for a generic is derived from node inheritance declarations and never set directly, and that `NodeInheritFromChecker` rejects removing a generic from a node's inheritance regardless of data. Record the symbols
- [ ] T011 Finalise the flip list from T003–T010. **Any family whose enforcement point could not be confirmed is removed from the flip list** and the finding recorded in `research.md` under a new "R9 — tracing outcome" section. Update `data-model.md`'s classification tables if the list changed

**Checkpoint**: The flip list is evidence-backed. Phases 3+ may begin.

---

## Phase 3: User Story 3 — The classification cannot drift silently (Priority: P2, sequenced first)

**Goal**: A developer adding a constraint checker is forced to state its classification, and the flip in Phase 5 becomes a reviewable diff rather than a silent change.

**Independent Test**: Add a bogus entry to `CONSTRAINT_VALIDATOR_MAP`; the test suite fails naming it. Remove it; the suite passes.

### Tests for User Story 3

> Written against **current** values so it passes immediately — this proves the harness is wired before it is used to police a change.

- [ ] T012 [US3] Create `backend/tests/unit/core/validators/test_constraint_classification.py` asserting **full dict equality** between `{identifier: checker.triggered_by_data_change for identifier, checker in CONSTRAINT_VALIDATOR_MAP.items()}` and a literal expected mapping of all 29 identifiers with today's values (27 `True`, 2 `False`). Full equality, not `issubset` and not "every identifier is present" — only equality fails on an *added* identifier (FR-004) and on a *removed* one (US3 acceptance scenario 2)
- [ ] T013 [US3] Prove the pinning test can fail: temporarily add a bogus entry to `CONSTRAINT_VALIDATOR_MAP` in `backend/infrahub/core/validators/__init__.py`, confirm `test_constraint_classification.py` fails naming the unclassified identifier, then remove the bogus entry. A full-dict-equality test built subtly wrong (comparing a dict against itself, or derived from the same source it pins) passes forever

**Checkpoint**: The classification is pinned and the pin is proven to bite.

---

## Phase 4: User Story 2 — A genuine schema property change still validates the full population (Priority: P1)

**Goal**: Prove the safety property *before* anything is removed, so the guard is a real regression test rather than a post-hoc rationalisation.

**Independent Test**: On a branch that changes an attribute's kind and also edits instance data for that kind, the kind constraint is present at unrestricted scope, sourced from the schema-diff producer.

### Tests for User Story 2

> **These must NOT live in `test_determiner.py`.** That file exercises `ConstraintValidatorDeterminer.get_constraints` — the *data-diff* producer — which after Phase 5 contributes nothing for these constraints. A test placed there would pass while FR-002 was entirely broken. The schema-diff producer is `MergeSchemaAnalyzer::calculate_validations`, composed by `ConstraintInfoMerger::merge`. There is currently **no test anywhere** covering `calculate_validations`.

- [ ] T014 [US2] Create `backend/tests/component/core/constraint_validators/test_schema_diff_constraints.py` covering `MergeSchemaAnalyzer::calculate_validations` composed with `ConstraintInfoMerger::merge`: on a source branch that changes an attribute's kind **and** edits instance data for that kind, assert the `attribute.kind.update` constraint is present with `node_uuids is None` (unrestricted scope). Assert the scope, not merely presence — presence alone would also hold if the data-diff producer supplied it, which is the opposite of what FR-002 requires
- [ ] T015 [P] [US2] Extend `test_schema_diff_constraints.py` with the destination-side case: the guarded property changes on the **destination** branch rather than the source, and the constraint is still contributed at unrestricted scope. This is what `get_3ways_diff_schema` (summing ancestor→source and ancestor→destination) exists for, and nothing currently tests it
- [ ] T016 [P] [US2] Extend `test_schema_diff_constraints.py` to cover a second value-intrinsic family beyond kind — pick one with a `parameters.*` identifier (regex or a length bound) — so the unrestricted-scope guarantee is not pinned on `attribute.kind.update` alone
- [ ] T017 [US2] Add one end-to-end case to `backend/tests/component/core/test_branch_rebase.py` (or `test_branch_merge.py`, whichever already has the closest fixture): rebase/merge a branch carrying both a guarded-property change and data changes, and assert the full-population validation still runs and reports correctly. Proves the composition in situ, not only in isolation
- [ ] T018 [US2] Run T014–T017 against the **unmodified** codebase and confirm they **pass**. This is the point of sequencing US2 before US1: a safety test that has only ever been run after the change it guards against is not a guard

**Checkpoint**: The safety property is proven to hold today. Any Phase 5 regression will now be caught.

---

## Phase 5: User Story 1 — Data-only branch operations skip checks that cannot fail (Priority: P1) 🎯 The deliverable

**Goal**: Remove value-intrinsic constraint scheduling from the data-diff producer.

**Independent Test**: A data-only diff schedules zero constraints from the value-intrinsic identifiers and every cross-node constraint, with total scheduled constraints falling by `2A + R + P`.

### Implementation for User Story 1

> One class attribute per checker, no logic changes. Only families that survived T011.

- [ ] T019 [P] [US1] Add `triggered_by_data_change = False` to `AttributeKindChecker` in `backend/infrahub/core/validators/attribute/kind.py`
- [ ] T020 [P] [US1] Add `triggered_by_data_change = False` to `AttributeOptionalChecker` in `backend/infrahub/core/validators/attribute/optional.py`
- [ ] T021 [P] [US1] Add `triggered_by_data_change = False` to `AttributeRegexChecker` in `backend/infrahub/core/validators/attribute/regex.py` — moves two identifiers (`attribute.regex.update`, `attribute.parameters.regex.update`)
- [ ] T022 [P] [US1] Add `triggered_by_data_change = False` to `AttributeLengthChecker` in `backend/infrahub/core/validators/attribute/length.py` — moves **four** identifiers (`min_length`, `max_length`, and both `parameters.*` variants)
- [ ] T023 [P] [US1] Add `triggered_by_data_change = False` to `AttributeEnumChecker` in `backend/infrahub/core/validators/attribute/enum.py`
- [ ] T024 [P] [US1] Add `triggered_by_data_change = False` to `AttributeChoicesChecker` in `backend/infrahub/core/validators/attribute/choices.py`
- [ ] T025 [P] [US1] Add `triggered_by_data_change = False` to `AttributeNumberChecker` in `backend/infrahub/core/validators/attribute/min_max.py` — moves **three** identifiers (`parameters.min_value`, `parameters.max_value`, `parameters.excluded_values`)
- [ ] T026 [US1] Add `triggered_by_data_change = False` to **`RelationshipPeerChecker` only** in `backend/infrahub/core/validators/relationship/peer.py`. ⚠️ This file defines **two** checkers — `RelationshipPeerParentChecker` (guarding `relationship.common_parent.update`) is cross-node and **must keep** its data trigger. Not parallel-safe with any other task in this file
- [ ] T027 [US1] Update the expected literal in `backend/tests/unit/core/validators/test_constraint_classification.py` to the post-flip values. **Same commit as T019–T026** — a pinning test updated separately is a pinning test that briefly did not pin. The diff of this literal is the reviewable record of exactly which identifiers moved

### Existing determiner test updates (six sites, per research R5)

> These shrink existing expected sets. The suite must be green after this group before new assertions are added.

- [ ] T028 [US1] In `backend/tests/component/core/constraint_validators/test_determiner.py`, update the `person_name_node_diff` fixture: drop the `attribute.kind.update` and `attribute.optional.update` entries, keep `attribute.unique.update`. Shared by five tests
- [ ] T029 [US1] In the same file, update the `person_cars_node_diff` fixture: drop the `relationship.peer.update` entry, keep cardinality, optional, min_count, max_count
- [ ] T030 [US1] In the same file, drop `"peer"` from the module-level `RELATIONSHIP_PROPERTIES` tuple
- [ ] T031 [US1] In the same file, update `test_uniqueness_not_triggered_by_unrelated_field`: drop the `kind` and `optional` attribute constraints, leaving only `unique`
- [ ] T032 [US1] In the same file, update `test_generic_uniqueness_triggered_by_inherited_field`: drop the `kind` and `optional` attribute constraints from the expected set
- [ ] T033 [US1] In the same file, update `test_node_property_constraints_included`: drop the `attribute.parameters.max_length.update` constraint from the expected set
- [ ] T034 [US1] Run `uv run pytest backend/tests/component/core/constraint_validators/test_determiner.py -q` and confirm green before proceeding

### New intentional assertions

> The Phase-5 shrinkage above proves the narrowing *by omission*. These state it *by intent*, which is what a reviewer can check.

- [ ] T035 [US1] Add a test to `test_determiner.py` for a data-only diff that asserts **zero** constraints from the value-intrinsic identifiers, naming the exclusion explicitly rather than relying on shrunken sets (FR-001, SC-001)
- [ ] T036 [US1] Add a test to `test_determiner.py` asserting **every** cross-node constraint is still scheduled for a data-only diff — attribute uniqueness, node uniqueness constraints, hierarchy parent/children, relationship cardinality/min_count/max_count/optional, common parent (FR-003)
- [ ] T037 [US1] Add a parameterised count assertion to `test_determiner.py` implementing SC-002's `2A + R + P` over diffs with known A/R/P compositions (A = attribute pairs, R = relationship pairs, P = set optional attribute parameters). Use the dataclass parametrize pattern with `name` as the first field per the project testing rules. This is the gate that makes the headline reduction claim CI-enforced rather than narrated
- [ ] T038 [US1] Re-run the US2 guard tests (T014–T017) and confirm they **still pass** after the flip. This is the regression check the whole US2-before-US1 ordering exists to enable

**Checkpoint**: The deliverable is in, narrowing is asserted by intent, and the safety property survived it.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Consistency, diagnosability, documentation, and the measurement the PR needs

- [ ] T039 [P] Normalise the two number-pool registry keys in `backend/infrahub/core/validators/__init__.py` from `ConstraintIdentifier.ATTRIBUTE_PARAMETERS_START_RANGE_UPDATE` / `..._END_RANGE_UPDATE` to their `.value` form, matching the other 27 entries. Behaviour-preserving — `ConstraintIdentifier` is a `StrEnum`, so member and value hash and compare identically (verified, research R4). Confirm `test_constraint_classification.py` still passes unchanged
- [ ] T040 [P] Add a DEBUG log at **both** classification skip sites in `backend/infrahub/core/validators/determiner.py` — in `_get_property_constraints_for_one_schema` and `_get_constraints_for_one_field` — naming the constraint and the reason. The skip is currently silent while both neighbouring skip paths log (kind-absent-from-schema at INFO, unmapped-validator at WARNING). This feature's one dangerous failure mode is a constraint silently not running; leaving this unlogged makes it undiagnosable
- [ ] T041 Create `dev/knowledge/backend/constraint-validation.md` covering: the two constraint producers and their **three differing call-site gates** (merge recomputes via `has_schema_changes()`, Proposed Change has no gate, rebase uses the cached `Branch.schema_differs_from_default_branch`); the determiner's two decision points; the merger's union-with-unrestricted-scope-winning rule; and the full classification with each entry's justification including the enforcement sites traced in T003–T010
- [ ] T042 Add to `dev/knowledge/backend/constraint-validation.md`: the **profile/template asymmetry** — the schema comparison excludes profile and template schemas, so those kinds rely on the write-time argument alone and the general "the schema-diff producer picks it up instead" claim does not hold for them; and the **per-checker classification limit** — all identifiers sharing a checker necessarily share a classification, and splitting the checker is the remedy if that ever stops holding
- [ ] T043 Add to `dev/knowledge/backend/constraint-validation.md` the R3 safety argument: why the rebase hash gate does not become a correctness gap (the argument turns on the candidate schema, not the gate), and the residual fail-open when a schema hash is absent. Recording it here is what stops the next reader re-deriving it
- [ ] T044 [P] Add a `housekeeping` changelog fragment under `changelog/` following the `+<slug>.housekeeping.md` convention. Use the `creating-changelog-entries` skill. Grep the actual diff before writing it — state what landed, not what the plan intended
- [ ] T045 Measure and record (SC-004): before/after wall-clock for a data-only rebase against a populated dev stack, **with the node population it was measured against**. Record in the knowledge page *and* the PR description — a figure that lives only in a PR description is not recoverable later
- [ ] T046 Run the full validation sweep from `quickstart.md`: the constraint, validator and migration suites, and confirm the pass count matches the T002 baseline plus the new tests
- [ ] T047 Run `uv run invoke format`, then `/pre-ci`. Note the repo caveat: `invoke lint` runs ruff over a subset of paths while CI runs `ruff check . --exclude python_sdk` repo-wide; `/pre-ci` covers the whole-repo check
- [ ] T048 Open the PR with the before/after measurement, the scheduled-constraint counts, and the list of identifiers whose classification changed (taken from the T027 diff, not from the plan)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: depends on Phase 1. **Blocks everything** — T011 can change the flip list, so no flip may precede it
- **Phase 3 (US3)**: depends on Phase 2. Must precede Phase 5 so the flip is a reviewable diff
- **Phase 4 (US2)**: depends on Phase 2. Must precede Phase 5 so its tests are a genuine regression guard (T018 runs them pre-change)
- **Phase 5 (US1)**: depends on Phases 3 and 4. The deliverable
- **Phase 6 (Polish)**: depends on Phase 5, except T039 and T040 which are independent of the flip

### Critical path

```text
T001 → T002 → T003..T010 (parallel) → T011 → T012 → T013 → T014..T017 → T018
     → T019..T026 (parallel) → T027 → T028..T033 → T034 → T035..T037 → T038
     → T041..T043 → T045 → T046 → T047 → T048
```

### Hard ordering constraints

| Constraint | Why |
|---|---|
| T011 before any of T019–T026 | Tracing can remove a family from the flip list |
| T012 before T027 | The pinning test must exist at current values before it records the change |
| T018 before T019 | A safety test never run pre-change is not a guard |
| T019–T026 and T027 in **one commit** | A pinning test updated separately briefly did not pin |
| T028–T033 all before T034 | The six sites fail as a group; partial updates leave a red suite |
| T038 after T019–T026 | It is the regression check on the flip |
| T045 after T019–T026 | "After" cannot be measured before the change |

### Parallel Opportunities

- **T003–T010** — eight independent tracing tasks, different modules. The largest parallel block
- **T019–T026** — eight checker files, one attribute each. T026 is [P] with the others but carries the two-checkers-in-one-file trap
- **T015, T016** — independent cases in the same new test file; parallel-safe if authored as separate functions
- **T039, T040** — different files, both independent of the flip
- **T044** — changelog fragment, independent of everything except knowing what landed

### Not parallel

- T028–T033 all touch `test_determiner.py`. Sequential
- T041–T043 all touch the same new knowledge page. Sequential
- T027 touches the same file T012 created, after T019–T026. Sequential

---

## Parallel Example: Phase 2 tracing

```bash
# Eight independent traces, one per constraint family:
Task: "Trace write-time enforcement for attribute kind"
Task: "Trace write-time enforcement for attribute optionality"
Task: "Trace write-time enforcement for attribute regex"
Task: "Trace write-time enforcement for attribute length bounds"
Task: "Trace write-time enforcement for attribute enum"
Task: "Trace write-time enforcement for attribute dropdown choices"
Task: "Trace write-time enforcement for attribute numeric bounds"
Task: "Confirm the relationship peer widening argument in code"
```

## Parallel Example: Phase 5 flips

```bash
# Eight checker files, one class attribute each:
Task: "AttributeKindChecker in attribute/kind.py"
Task: "AttributeOptionalChecker in attribute/optional.py"
Task: "AttributeRegexChecker in attribute/regex.py"
Task: "AttributeLengthChecker in attribute/length.py"
Task: "AttributeEnumChecker in attribute/enum.py"
Task: "AttributeChoicesChecker in attribute/choices.py"
Task: "AttributeNumberChecker in attribute/min_max.py"
Task: "RelationshipPeerChecker ONLY in relationship/peer.py"   # not PeerParent
```

---

## Implementation Strategy

### Recommended: single increment

This feature does not decompose into independently shippable slices, and the tasks are not written as though it does. US1 alone is a validation removal with no guard; US2 and US3 alone change nothing user-visible. Ship all three together.

The useful checkpoints are not delivery points but **verification points**:

1. **After T011** — the classification is evidence-backed rather than asserted. If a family failed tracing, the scope shrinks here, and that is the cheapest possible moment to discover it
2. **After T018** — the safety net exists and has been observed to pass. Nothing has been removed yet
3. **After T034** — the flip is in and the existing suite is green
4. **After T038** — the safety net survived the flip. This is the moment the feature is *known* to be correct
5. **After T047** — CI-ready

### If the work must be split across sessions

Split at checkpoint 2 (after T018) or checkpoint 4 (after T038). Never split inside T019–T027 — the flip and the pinning-test update belong in one commit. Never split inside T028–T033 — the six sites fail as a group.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks
- Per `.agents/rules/code-doc-style.md`: **no ticket IDs, spec IDs, or task IDs in source, docstrings, or test names.** FR/SC/T references belong in commit messages, the PR description, and this file only
- Per `.agents/rules/testing-python.md`: no mocking. The determiner component test already uses a hand-written `_NoDependentsResolver` adapter — follow that pattern
- Assert exact collections (full set/dict equality), never `in` or non-emptiness
- Commit after each logical group; respect the two "same commit" constraints above
- The `filter_invalid` dead parameter on `get_constraints` is **deliberately out of scope** (critique E2). Do not remove it here
