---
description: "Task list for Entities Clean-Architecture Migration"
---

# Tasks: Entities Clean-Architecture Migration

**Input**: Design documents from `/specs/001-entities-arch-migration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: No new test authoring requested — this is a behavior-preserving refactor. Each migration task **runs the existing suites** (`pnpm test`) as part of verification; no new test files are created except where a moved file's test moves with it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (independent entity, different files)
- Paths are under `frontend/app/` unless noted.

**Governance note**: Every user-story task below (except the sub-tasks of a single entity) corresponds to **one pull request** off trunk, green on `pnpm tsc && pnpm build && pnpm test && pnpm biome` before merge (FR-011). All PRs append to the shared `frontend/app/biome.jsonc` `overrides.includes` list — that shared edit **serializes at merge time** (rebase/resolve the one-line append), even though the entity code changes are independent.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the branch and the guard scaffold.

- [X] T001 Confirm work is on a fresh branch off trunk (not the planning branch) and read `specs/001-entities-arch-migration/{plan.md,data-model.md,contracts/,quickstart.md}` before starting.
- [X] T002 Add an empty Tier-1 guard scaffold to `frontend/app/biome.jsonc`: an `overrides` entry with an empty `includes: []` and the `noRestrictedImports` rule block per `contracts/biome-guard.md` (no entity globs yet, so it is inert and `pnpm biome` still passes).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lock the exact guard rule so every user story can append to it.

**⚠️ CRITICAL**: No entity migration can begin until the rule definition is final.

- [X] T003 In `frontend/app/biome.jsonc`, finalize the `noRestrictedImports` rule for the guard: confirm the correct rule group/keys against `@biomejs/biome@2.4.16`, and populate the forbidden set — `@apollo/client`, `@tanstack/react-query`, `react`, `**/graphql/generated/**`, `shared/api/rest/types.generated`, browser storage (`localStorage`/`sessionStorage`, jotai/zustand store modules), and notification/toast libraries — with clear messages. Verify `pnpm biome` passes with the still-empty `includes`.

**Checkpoint**: Guard rule defined and inert — entity migrations can begin.

---

## Phase 3: User Story 1 — role-manager mechanics shakeout (Priority: P1) 🎯 MVP

**Goal**: Migrate the smallest entity and prove the folder mechanics + live guard end-to-end.

**Independent Test**: Migrate `role-manager` alone; `pnpm tsc && pnpm build && pnpm test && pnpm biome` all green; the guard fails when a forbidden import is temporarily added to a migrated `domain/` file.

- [X] T004 [US1] Survey `src/entities/role-manager/` and classify its 2 domain files (`get-decision-options.ts`, `get-decision-options.test.ts`) per the `data-model.md` heuristic (pure fn → `rules/`); confirm it is below the >4 split threshold and will **stay flat**.
- [X] T005 [US1] Ensure no `src/entities/role-manager/domain/**` file imports a generated type, React, TanStack, Apollo, storage, or toast lib; move any transport/mapping into `src/entities/role-manager/api/` (creating `api/` only if needed), keeping `domain/` flat.
- [X] T006 [US1] Rewrite all import sites repo-wide affected by any moves in T005 (search `@/entities/role-manager/...`).
- [X] T007 [US1] Append `src/entities/role-manager/domain/**` to `overrides.includes` in `frontend/app/biome.jsonc`.
- [X] T008 [US1] **Guard liveness test** (one-time): temporarily add a `@tanstack/react-query` import to a `role-manager/domain` file, run `pnpm biome`, confirm it **fails**, then revert (per `contracts/biome-guard.md`).
- [X] T009 [US1] Verify `pnpm tsc && pnpm build && pnpm test && pnpm biome` all green; open the PR (diff = `role-manager` + one lint-config line).

**Checkpoint**: Pattern + guard validated on a trivial entity. MVP reached.

---

## Phase 4: User Story 2 — branches canonical reference (Priority: P1)

**Goal**: Exercise every hard case (mapper split, generated-leak fix, >4 domain split) and document the result as the copyable template.

**Independent Test**: `branch.mappers.ts` split (types → `domain/model/`, mapping → `api/`); all gates green; knowledge doc updated.

> **DECISION LOG (2026-07-02):** (1) The **Tier-1 Biome guard was dropped** at the user's instruction — enforcement is now **review-only** (T017 and FR-010 are N/A). (2) **Generated enums / node value-types** (e.g. `BranchStatus`) **are allowed in `domain/model`**; only wire-shape response DTOs + mappers move to `api/` (redefines T014's "pure leaf" as free-of-sibling-layers, not free-of-generated). (3) Mappers moved to `api/` but are still **called by** use-cases (option-b); `api/` fetchers still return raw `{data,errors}` — full "fetchers return domain types" (T012/FR-002) is a further optional step, not done. (4) The project has no green `tsc` gate; the real gate is **`betterer`** (ratchet at 208).

- [X] T010 [US2] Survey `src/entities/branches/` (11 domain files) and produce the classification map.
- [X] T011 [US2] Split `branch.mappers.ts`: domain types → `domain/model/branch.ts`; mapping fns + `InfrahubBranchResponse` DTO → `api/branch.mappers.ts`; filter helpers → `domain/rules/branch-filters.ts`.
- [~] T012 [US2] **Deviated (option-b):** mappers live in `api/` and are called by use-cases; fetchers still return raw `{data,errors}`. Full FR-002 (fetchers return domain types) deferred.
- [X] T013 [US2] Move the 10 orchestration files into `domain/use-cases/`. (model/ and rules/ hold 1 file each — accepted for the reference to show all three layers.)
- [~] T014 [US2] `domain/model/branch.ts` imports nothing from `api/`/`rules/`/`use-cases/`/`ui/` ✅; it **does** import generated `BranchStatus` (allowed per decision (2)).
- [~] T015 [US2] `store`/`branchesState` read still in `use-cases/get-branches.ts` (deferred, FR-016). Guard dropped → no exclusion needed.
- [X] T016 [US2] Rewrite all repo-wide import sites (29 files: 18 external type-only → `model/branch`, 11 `ui/queries` → `use-cases/`).
- [N/A] T017 [US2] Guard dropped — no glob appended.
- [X] T018 [US2] Gates green: `biome` clean, branches unit tests 15/15, `betterer` stable at 208 (baseline refreshed for moved files). `vite build` not re-run.
- [X] T019 [US2] Updated `dev/knowledge/frontend/entities-structure.md` from the `branches` result (new tree, layer-rule table, mappers-in-api, generated-DTO-vs-enum rule, review-only enforcement, branches worked example).

**Checkpoint**: Canonical reference exists and is documented — fan-out can copy it.

---

## Phase 5: User Story 3 — fan out across remaining entities (Priority: P2)

**Goal**: Converge every remaining non-`nodes/` entity on the reconciled structure. **One PR per entity**, each following `quickstart.md` and the `branches` template. Each task = {survey → classify → split mappers to `api/` & types to `model/` → purge generated from `domain/` → split `domain/` if >4 files (else flat) → rewrite imports → append guard glob → verify all four commands}.

- [X] T020 [P] [US3] Migrate `src/entities/artifacts/`.
- [X] T021 [P] [US3] Migrate `src/entities/authentication/`.
- [X] T022 [P] [US3] Migrate `src/entities/config/` (2 domain files → stays flat).
- [ ] T023 [P] [US3] Migrate `src/entities/diff/` (has a `diff/utils/` — rename to meaningful files/rules per naming guidance).
- [X] T024 [P] [US3] Migrate `src/entities/events/`.
- [X] T025 [P] [US3] Migrate `src/entities/generators/`.
- [X] T026 [P] [US3] Migrate `src/entities/graphql/` (ui-only; no `domain/` → no guard glob, verify only).
- [X] T027 [P] [US3] Migrate `src/entities/groups/`.
- [X] T028 [P] [US3] Migrate `src/entities/homepage/` (ui-only; verify only).
- [X] T029 [P] [US3] Migrate `src/entities/ipam/` (sub-modules `ip-addresses`, `ip-namespaces`, `ip-prefixes`, `ipam-tree` — treat as one entity with internal structure; do not flatten sub-features into one `ui/`).
- [X] T030 [P] [US3] Migrate `src/entities/navigation/` (has `navigation/stores/` — keep store in `ui/` layer, out of `domain/`).
- [X] T031 [P] [US3] Migrate `src/entities/object-file/`.
- [X] T032 [P] [US3] Migrate `src/entities/path-traversal/`.
- [X] T033 [P] [US3] Migrate `src/entities/permission/` (has `permission/queries/` — fold into `api/` or `ui/queries/` per layer rules).
- [X] T034 [P] [US3] Migrate `src/entities/proposed-changes/` (8 domain files → split; has `stores/` and `utils/` to reclassify).
- [X] T035 [P] [US3] Migrate `src/entities/repository/`.
- [X] T036 [P] [US3] Migrate `src/entities/resource-manager/` (has `resource-manager/utils/` to reclassify).
- [ ] T037 [P] [US3] Migrate `src/entities/schema/` (8 domain files → split; `get-schema-hash`/`add-*`/`remove-*` → `rules/`, `get-/load-schema` → `use-cases/`; has `stores/` + `utils/`).
- [X] T038 [P] [US3] Migrate `src/entities/tasks/`.
- [X] T039 [P] [US3] Migrate `src/entities/triggers/` (ui-only; verify only).
- [X] T040 [P] [US3] Migrate `src/entities/user-profile/`.

**Checkpoint**: All entities except `nodes/` migrated; guard covers all migrated `domain/` folders.

---

## Phase 6: User Story 4 — nodes/ namespace, last (Priority: P3)

**Goal**: Migrate the `nodes/` namespace as its own multi-PR sub-epic without disturbing in-flight sort work. **One PR per sub-module.** Same per-entity recipe as US3.

- [ ] T041 [US4] Plan the `nodes/` sub-epic: enumerate sub-modules and loose top-level files (`getObjectItemDisplayValue.tsx`, `types.ts`, `utils.ts`, `stores/`), decide their target homes, and sequence PRs smallest-first.
- [ ] T042 [P] [US4] Migrate `src/entities/nodes/edit-form-hook/` (2 files).
- [ ] T043 [P] [US4] Migrate `src/entities/nodes/object-items/` (1 file) and `src/entities/nodes/object-item-details/` (2 files).
- [ ] T044 [P] [US4] Migrate `src/entities/nodes/object-template/` (2 files) and `src/entities/nodes/profiles/` (4 files).
- [ ] T045 [P] [US4] Migrate `src/entities/nodes/object-item-meta-edit/` (4 files) and `src/entities/nodes/object-item-edit/` (6 files).
- [ ] T046 [P] [US4] Migrate `src/entities/nodes/hierarchy/` (12 files).
- [ ] T047 [P] [US4] Migrate `src/entities/nodes/convert/` (21 files).
- [ ] T048 [P] [US4] Migrate `src/entities/nodes/relationships/` (46 files).
- [ ] T049 [US4] Migrate `src/entities/nodes/object/` (169 files) — the largest; **must not disturb in-flight sort work** (`domain/sort.ts`, `domain/rules/`, `ui/sort/`); confirm sort tests stay green. Likely several PRs.
- [ ] T050 [US4] Reclassify `nodes/` loose files and `nodes/stores/` into the appropriate entity layers; remove the now-empty namespace-level scaffolding.

**Checkpoint**: Entire `entities/` folder on the reconciled structure.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T051 Full-repo verification: `pnpm tsc && pnpm build && pnpm test && pnpm biome` green on trunk after all merges; confirm 0 `domain/**` files import generated types (SC-001/SC-002).
- [ ] T052 Confirm the Tier-1 `overrides.includes` list covers every migrated entity's `domain/**` and no unmigrated path (SC-004).
- [ ] T053 [P] File the deferred follow-up (FR-016): lift `store`/`branchesState` reads out of `domain/` into `ui/` for `branches` and any other flagged entity; remove their guard exclusions.
- [ ] T054 [P] Propose Tier-2 enforcement (dependency-cruiser) as a separate new-dependency decision per AGENTS.md ask-first gate: directional rules from `contracts/dependency-rules.md` (model-as-leaf, `api → domain/model` only, no cross-entity `api/`, no cycles).
- [ ] T055 Final pass on `dev/knowledge/frontend/entities-structure.md` to reflect the completed end-state (all entities + `nodes/`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)**: T003 must finalize the guard rule before any entity appends a glob.
- **US1 (Phase 3)** must complete first — it validates the pattern and guard (the liveness test T008 is done once here).
- **US2 (Phase 4)** should follow US1 and complete before the fan-out, because T019 produces the documented template the fan-out copies.
- **US3 (Phase 5)** depends on US2's documented template. The 20 entity tasks are mutually independent in code (`[P]`), but each appends to the shared `biome.jsonc` — serialize that one-line append at merge.
- **US4 (Phase 6)** runs last (FR-013); T049 depends on the in-flight sort work being settled.
- **Polish (Phase 7)** after all migrations merge.

### Parallel Opportunities

- Within US3, T020–T040 can be worked in parallel by different developers (independent entities); merge-order only matters for the `biome.jsonc` append.
- Within US4, T042–T048 sub-modules are largely independent; T049 (`nodes/object`) is the serialization point and coordinates with sort work.

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup) → Phase 2 (Foundational guard rule).
2. Phase 3 (US1 `role-manager`) → **STOP & VALIDATE**: guard is live, four commands green.
3. Phase 4 (US2 `branches`) → documented reference template.

### Incremental Delivery

Each entity PR (US3) and each `nodes/` sub-module PR (US4) is an independent, shippable increment that leaves the app green. `nodes/object` (T049) may span multiple PRs.

---

## Notes

- No new test files authored; each task runs `pnpm test` and preserves existing tests (they move with their subjects).
- ui-only entities (`graphql`, `homepage`, `triggers`) have no `domain/` → no guard glob; verification only.
- `[P]` = independent entity/different files; the shared `biome.jsonc` append is the one cross-task contention point.
- Every PR: diff ≈ one entity + one lint-config line; confirm no Towncrier fragment needed (internal refactor).
