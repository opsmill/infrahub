---

description: "Task list for Number Pools P1 — several weighted ranges per pool"
---

# Tasks: Number Pools — Several Weighted Ranges per Pool (P1)

**Epic**: [IFC-3065 — Number pool improvements - part 1 - Weighted Ranges per pool](https://opsmill.atlassian.net/browse/IFC-3065)

**Input**: Design documents from `specs/ifc-3065-number-pool-ranges/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graphql-schema-changes.md, quickstart.md

**Tests**: Included — the Infrahub constitution (Principle IV) mandates tests alongside implementation.

**Organization**: Grouped by user story (US1–US3 from spec.md). Foundational work (the new range kind, the effective-space calculator, the data migration) blocks all three stories and comes first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks).
- Code sites are named by module + symbol, never line numbers (`dev/guidelines/documentation.md`).

## Path Conventions

Backend-only slice. Source under `backend/infrahub/`, tests under `backend/tests/`.

---

## Phase 1: Setup & De-risk (Shared)

**Purpose**: Prove the load-bearing schema assumption before building on it (critique E1/X1).

- [ ] T001 Write a fail-fast schema-load/component test in `backend/tests/component/core/resource_manager/test_number_pool_range_schema.py` proving an `AGNOSTIC` node can inherit the `AWARE` generic `CoreWeightedPoolResource` and that `allocation_weight` materialises — run it against the draft kind before any query/migration work.
- [ ] T002 Based on T001's outcome, record the branch-inheritance decision inline in `research.md` (D2): either confirm the AGNOSTIC-inherits-AWARE mix is valid, or apply the fallback (make `CoreWeightedPoolResource` branch-neutral for inheritance in `backend/infrahub/core/schema/definitions/core/resource_pool.py`). Do not proceed to Phase 2 until resolved.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new range kind, the single effective-space calculator, and the data migration — every user story depends on these.

**⚠️ CRITICAL**: No user-story phase may begin until Phase 2 is complete.

### Schema: new kind, relationship, shorthand

- [ ] T003 Declare `CoreNumberPoolRange` (`start`, `end` Number required; `inherit_from=[CoreWeightedPoolResource]`; `branch=AGNOSTIC`) in `backend/infrahub/core/schema/definitions/core/resource_pool.py`, and register it in `backend/infrahub/core/schema/definitions/core/__init__.py`.
- [ ] T004 Add the `ranges` relationship (cardinality many → `CoreNumberPoolRange`) on `core_number_pool` and the mandatory `pool` back-relationship (cardinality one) on `CoreNumberPoolRange` in `backend/infrahub/core/schema/definitions/core/resource_pool.py`.
- [ ] T005 Change `start_range` and `end_range` on `core_number_pool` from required to `optional=True` in `backend/infrahub/core/schema/definitions/core/resource_pool.py`.
- [ ] T006 Regenerate protocols and generated schema (`uv run invoke backend.generate`) and commit `backend/infrahub/core/protocols.py` (new `CoreNumberPoolRange`, nullable pool scalars) and any generated schema files.

### Effective-space calculator (single source of truth)

- [ ] T007 Implement the effective-space calculator in `backend/infrahub/pools/number.py`: a pure structure computing (union of ranges) ∩ `[min_value, max_value]` − intersecting exclusions, exposing size, ordered effective ranges (by descending `allocation_weight`, then ascending value), and fullness; zero-safe (size 0 → not a division error). Reimplement `total_pool_size` and the three `utilization` properties on top of it.
- [ ] T008 [P] Unit-test the effective-space calculator in `backend/tests/unit/pools/test_effective_space.py`: min/max clamping, intersecting vs non-intersecting exclusions, empty result (size 0), single vs multiple ranges, weight ordering.

### Shorthand write/read

- [ ] T009 Implement the `start_range`/`end_range` write-shorthand (create-or-replace the single range) and read behaviour (return bounds only when exactly one range, else null) in the number-pool node/GraphQL resolution path (`backend/infrahub/core/node/resource_manager/number_pool.py` and the pool mutation/resolver in `backend/infrahub/graphql/mutations/resource_manager.py`).

### Data migration

- [ ] T010 Add graph data migration `m0NN_number_pool_single_range.py` in `backend/infrahub/core/migrations/graph/` (modelled on `m066_consolidate_duplicate_number_pools`, `ArbitraryMigration`): for each `CoreNumberPool`, create one `CoreNumberPoolRange` covering `[start_range, end_range]` (weight absent), linked via `ranges`; leave `IS_RESERVED`/`HAS_SOURCE` untouched; idempotent (never creates a second covering range). Register `Migration0NN` in `backend/infrahub/core/migrations/graph/__init__.py` with `minimum_version`.
- [ ] T011 [P] Migration test in `backend/tests/component/core/migrations/graph/test_0NN_number_pool_single_range.py` (modelled on `test_066_...`): existing single-span pool → one covering range and still allocatable (SC-005); re-running the migration is a no-op (E5 idempotency).

**Checkpoint**: New kind loads, calculator is unit-tested, existing pools migrate. User stories can now proceed.

---

## Phase 3: User Story 1 — Allocate across several weighted ranges with gaps (Priority: P1)

**Goal**: Allocation draws from several weighted ranges, falls through gaps, and reports full only when the whole effective space is consumed.

**Independent test**: Two ranges with a gap; exhaust the first; next allocation returns the first free value of the second range; full only when both are exhausted.

- [ ] T012 [US1] Generalise `NumberPoolGetFree` in `backend/infrahub/core/query/resource_manager.py` to a range set: the value-in-range filter becomes an `ANY`/`OR` over the ordered union of ranges, and the gap walk resumes at the next range's start after exhausting one; keep gap detection in Cypher; parameters become a list of `{start,end,weight}`.
- [ ] T013 [US1] Update `CoreNumberPool.get_next` in `backend/infrahub/core/node/resource_manager/number_pool.py` to drive allocation from the effective-space calculator and the range set — replace the inline `effective_start`/`effective_end` maths and the `skip_excluded` closure with calls into the calculator; select ranges by descending weight, lowest free value within the chosen range.
- [ ] T014 [US1] Update `NumberPoolGetTaken` (`backend/infrahub/core/query/resource_manager.py`) and the `get_taken` hook in `get_next` to operate over the range set (FR-011) — **keep** the `attribute.unique` skip behaviour (do not delete it; the #10180 revert is deferred to P2).
- [ ] T015 [US1] Generalise the mutation guard in `InfrahubNumberPoolMutation` (`backend/infrahub/graphql/mutations/resource_manager.py`) to validate each range (`start ≤ end`) and refuse intra-pool overlaps (FR-004); allow cross-pool overlap.
- [ ] T016 [US1] Enforce the same range-validity rules (`start ≤ end`, intra-pool non-overlap) in `NumberPoolParameters` validation in `backend/infrahub/core/schema/attribute_parameters.py`, and add the optional schema-declared `ranges` list plus the both-spellings-conflict validator; change `start_range`/`end_range` defaults to `None` (FR-039/FR-041; critique E2).
- [ ] T017 [P] [US1] Component tests in `backend/tests/component/core/resource_manager/test_number_pool.py`: fall-through across a gap returns 205 (SC-001), full only when all ranges exhausted, weighted range selection, and the FR-011 taken-value skip still working over the range set.
- [ ] T018 [P] [US1] Query-level tests in `backend/tests/component/core/resource_manager/test_number_pool_query.py` for the range-set `NumberPoolGetFree`/`GetTaken` shape.
- [ ] T019 [P] [US1] Range-validity validator test in `backend/tests/component/pools/test_schema_number_pool_upserter.py` (or a sibling) covering schema-created pools refusing inverted/overlapping ranges and the both-spellings conflict.
- [ ] T020 [P] [US1] `EXPLAIN` + at-scale allocation benchmark for the generalised gap walk over a fully-allocated multi-range pool (e.g. 4094-entry VLAN) in `backend/tests/query_benchmark/` (critique E3/E4).

**Checkpoint**: Weighted multi-range allocation with gap fall-through works end-to-end.

---

## Phase 4: User Story 2 — Edit ranges without refusal; retention; zero ranges (Priority: P1)

**Goal**: Range add/remove is never refused; a number left outside all ranges is retained and hidden; a pool with zero ranges is legal and reports full.

**Independent test**: Allocate inside a range, remove it — removal succeeds, the number stays associated, is excluded from utilization, never handed out; re-add the range — it counts again; remove the last range — pool legal, 0/0, allocation raises pool-exhausted.

- [ ] T021 [US2] Ensure range removal never deletes held-number records: confirm the `ranges` relationship removal path leaves `IS_RESERVED`/`HAS_SOURCE` untouched, and that the effective-space read path filters retained out-of-range numbers (FR-002/FR-002a) — adjust `backend/infrahub/core/node/resource_manager/number_pool.py` / the read queries as needed.
- [ ] T022 [US2] Generalise `NumberPoolGetUsed` and `NumberPoolGetAllocated` in `backend/infrahub/core/query/resource_manager.py` to the range set, so used/allocated counts include only numbers inside a current effective range (retained out-of-range numbers excluded from utilization).
- [ ] T023 [US2] Handle the zero-ranges / empty-effective-space case in `backend/infrahub/core/node/resource_manager/number_pool.py` and `backend/infrahub/pools/number.py`: utilization reports 0 of 0 (0%), allocation raises `PoolExhaustedError` (no division), a range clamped to empty counts as exhausted (D11/FR-007).
- [ ] T024 [P] [US2] Component tests in `backend/tests/component/core/resource_manager/test_number_pool.py`: remove a range holding 250 → 101 of 101, 250 never handed out, re-add restores it (SC-002/FR-002a); zero ranges → 0% and pool-exhausted on allocate (SC-006).
- [ ] T025 [P] [US2] Functional test in `backend/tests/functional/pools/test_numberpool_branch.py`: range add/remove is branch-agnostic — takes effect on every branch immediately.

**Checkpoint**: Ranges are safely editable in production; accounting stays correct across removal, retention, and re-add.

---

## Phase 5: User Story 3 — Consistent size, utilization & fullness (Priority: P1)

**Goal**: One consistent answer for size/utilization/fullness across every read path, honouring the attribute domain, with no divide-by-zero.

**Independent test**: Ranges partly outside `[min,max]` with some exclusions inside and some outside; size/utilization equal the effective space consistently; the former divide-by-zero case returns a correct size.

- [ ] T026 [US3] Route the size/utilization/fullness read paths (`backend/infrahub/pools/number.py` and the `NumberUtilizationGetter` caller) through the effective-space calculator so min/max sensitivity and intersecting-exclusion behaviour are consistent everywhere (FR-006/FR-008).
- [ ] T027 [US3] Update `AttributeNumberPoolChecker` and `AttributeNumberPoolUpdateValidatorQuery` in `backend/infrahub/core/validators/attribute/number_pool.py` to validate object values against the range set (outside *every* range) rather than a single span, identifying offending objects (FR-039).
- [ ] T028 [P] [US3] Component tests in `backend/tests/component/core/resource_manager/test_number_pool.py`: effective space honours min/max and only intersecting exclusions (SC-003); the former divide-by-zero (exclusions entirely outside the ranges) returns a correct non-zero size (SC-004); `start_range`/`end_range` read bounds for one range and null for many (SC-007).
- [ ] T029 [P] [US3] Validator test in `backend/tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py` for the range-set domain check (FR-039).

**Checkpoint**: Utilization and fullness are trustworthy and consistent; the divide-by-zero defect is gone.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T030 [P] Add Towncrier changelog fragments in `changelog/`: utilization now sensitive to `min_value`/`max_value` and to which excluded values intersect the ranges; `start_range`/`end_range` read as null on a pool with more than one range. (The #10180-revert entry belongs to P2, not here.) Use the `creating-changelog-entries` skill; Vale-lint them.
- [ ] T031 [P] Verify existing frontend/API consumers tolerate a null `start_range`/`end_range` and ensure the changelog upgrade note addresses API consumers (critique P1/X2). If a UI panel binds the field non-null, file a P2 follow-up rather than expanding this slice.
- [ ] T032 Regenerate published schema/contract artifacts and commit: `uv run invoke schema.generate-graphqlschema` (`schema/schema.graphql`), `uv run invoke schema.generate-jsonschema` (`schema/openapi.json`), `uv run invoke docs.generate`, and `cd frontend/app && pnpm codegen`.
- [ ] T033 [P] Update `dev/knowledge/backend/` with the ranges model and the effective-space calculator (source of truth for size/utilization/order/fullness).
- [ ] T034 Run `/pre-ci` (format, lint, unit, generated-file + generated-doc validation) and fix any drift before pushing.

---

## Dependencies & Execution Order

- **Phase 1 (T001–T002)** must complete first — it de-risks the whole kind.
- **Phase 2 (T003–T011)** blocks all user stories. Within it: T003→T004→T005→T006 (schema then regen) run before query/behaviour work; T007→T008 (calculator) and T010→T011 (migration) can proceed in parallel with each other after the schema exists; T009 (shorthand) needs T003–T005.
- **Phase 3 / 4 / 5** are all Priority P1 and share the foundation; recommended order is US1 → US2 → US3 (allocation, then edit/retention, then reporting), but US2 and US3 have few hard cross-dependencies once Phase 2 lands and may proceed in parallel by different developers. US3's validator (T027) is independent of US1/US2.
- **Phase 6** last — generated files and changelog reflect the final code.

## Parallel Opportunities

- Phase 2: T008 (calculator unit tests) ∥ T010/T011 (migration) once the schema (T003–T006) exists.
- Phase 3: T017, T018, T019, T020 are all `[P]` (distinct test files).
- Phase 4: T024 ∥ T025. Phase 5: T028 ∥ T029.
- Phase 6: T030, T031, T033 are `[P]`; T032 and T034 are serial gates.

## Implementation Strategy (MVP first)

- **MVP = Phase 1 + Phase 2 + Phase 3 (US1)**: weighted multi-range allocation with gap fall-through over migrated pools — the core capability, independently demonstrable.
- **US2** makes ranges safely editable (retention, zero ranges) — required before release but layered on US1.
- **US3** makes reporting trustworthy and removes the divide-by-zero — completes the slice.
- P1 is independently *releasable* (FR-011 keeps the taken-value skip); it is not the whole Number Pools feature (P2/P3 follow on their own branches).
