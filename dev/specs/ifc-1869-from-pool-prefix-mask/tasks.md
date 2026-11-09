---
description: "Task list for: Custom prefix mask for from-pool allocation"
---

# Tasks: Custom prefix mask for from-pool allocation

**Input**: Design documents from `specs/ifc-1869-from-pool-prefix-mask/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Jira**: IFC-1869

**Tests**: Included — the constitution's Test Discipline requires FE unit, E2E, and backend tests for user-facing features.

**Organization**: Tasks grouped by user story. Phase 3 (US1 MVP) is independently shippable with zero backend change. Phase 4 extends US1 to the remaining entry points and is gated on maintainer sign-off for a GraphQL input change.

## Status (as built)

Scope shipped: **IP address pools only.** Key deltas from the task plan below:

- **Phase 4 (T014–T019) — DEFERRED.** IP prefix pools use `size`, not `prefixlen`; supporting them needs an Ask-First GraphQL change. The UI hides the control for prefix pools instead. Not implemented.
- **FR-014 conflict guard (added, not originally a task):** `CoreIPAddressPool.get_resource` rejects an explicit `prefixlen` that conflicts with an existing reservation. This replaced the "unsatisfiable-length" framing in T024.
- **Design delta:** `PoolPrefixLengthInput` props are `value/placeholder/invalid/onChange` and it renders **inside `PoolSelect`** (gated to `CoreIPAddressPool`), not in the three host fields. `getFormFieldFrom*` were not extended (T006). No family-aware validation (T023 uses range 1–128).
- **E2E (T013, T019, T022, T026) — NOT done.** Verified manually in the live preview; Playwright specs are still outstanding.
- Changelog fragment is `changelog/+ifc-1869-from-pool-prefix-length.added.md` (T001).

## Path Conventions

Web app: `frontend/app/src/...` (frontend), `backend/infrahub/...` (backend). Paths below are repository-relative.

---

## Phase 1: Setup

- [x] T001 [P] Add towncrier changelog fragment (shipped as `changelog/+ifc-1869-from-pool-prefix-length.added.md`) describing the optional from-pool prefix-length control.
- [ ] T002 [P] Confirm the E2E dataset exposes the IP address and IP prefix pools used by `frontend/app/tests/e2e/ipam/ip-address-create-with-pool.spec.ts` and `ip-prefix-create-with-pool.spec.ts`; reuse existing fixtures, add none if they suffice.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ Blocks all user-story work.**

- [x] T003 Backend allocation-path audit. Finding: IP prefix pools expose `size` (not `prefixlen`) on their inline input, so the prefix/attribute paths need a GraphQL change — this is why Phase 4 was deferred and the scope narrowed to IP address pools.
- [x] T004 Extend `PoolValue` and the `from_pool` value on `AttributeValueFromPool` / `RelationshipValueFromPool` with optional `prefixlen?: number` in `frontend/app/src/shared/components/form/type.ts`.
- [x] T005 [P] Add `default_prefix_length { value }` to the IP-pool list query in `frontend/app/src/entities/nodes/relationships/api/generate-relationship-list.query.ts` (additive; no change for non-IP pools).
- [ ] T006 ~~Surface `defaultPrefixLength`/`addressFamily` on field `pool` metadata in `getFormFieldFrom*`~~ — **descoped.** The default reaches the control via the list query (T005) shown as a placeholder; no `addressFamily` plumbing (validation uses a fixed 1–128 range). Pin the family source explicitly: derive `addressFamily` (`"v4"`/`"v6"`) from the pool's default allocated object kind / IP namespace IP version **only if** the pool query exposes it (extend T005 to fetch that field if so); otherwise set `addressFamily = undefined` so validation falls back to 0–128 (FR-007). Do not guess v4.

**Checkpoint**: types + pool default available — control work can begin.

---

## Phase 3: User Story 1 — Allocate with a custom prefix length (Priority: P1) 🎯 MVP

**Goal**: A user selects an IP pool, enters a non-default prefix length, and the allocated object uses it. Proven end-to-end via the IP-address relationship path, which the backend already supports — zero backend change in this phase.

**Independent Test**: On a device's *Primary IP Address*, allocate from an address pool with length `/32`, save, and confirm the allocated address is `/32`.

- [x] T007 [US1] Create the shared control `frontend/app/src/shared/components/form/pool-prefix-length-input.tsx` (`PoolPrefixLengthInput`): props `poolKind`, `defaultPrefixLength`, `addressFamily`, `value`, `onChange`; visible only when a pool is selected and `poolKind` ∈ {`CoreIPAddressPool`, `CoreIPPrefixPool`}; leading `/` adornment via `Input`+`Row`; label "Prefix length · optional"; `data-testid="pool-prefix-length-input"`. Render it beside `PoolSelect` (under the "allocated by pool" state) in all three IP host fields: `frontend/app/src/shared/components/form/fields/input.field.tsx` (IP `prefix`/`address` attribute), `.../fields/relationships/regular-relationship.field.tsx`, and `.../fields/relationships/relationship-hierarchical.field.tsx`. Do NOT touch `pool-selector.tsx`/`number.field.tsx` (number pools — excluded by FR-003).
- [x] T008 [US1] Carry `prefixlen` into the emitted `PoolValue.from_pool`: thread the control's value through each host field's existing `onChange` (`updateAttributeFieldValue` / relationship `onChange`) and via `frontend/app/src/shared/components/inputs/pool-select.tsx`. Reset `prefixlen` to `undefined` when the selected pool changes (FR-009) and discard it when the pool is cleared / manual entry resumes (FR-010).
- [x] T009 [US1] Emit `prefixlen` (when present) in `frontend/app/src/shared/components/form/utils/mutations/getCreateMutationFromFormData.ts` for both the direct `from_pool` and `fromPoolRelationshipName` paths.
- [x] T010 [US1] Emit `prefixlen` (when present) in `frontend/app/src/shared/components/form/utils/mutations/getUpdateMutationFromFormData.ts`.
- [x] T011 [P] [US1] Vitest: mutation builders include `prefixlen` when set and omit it when empty — `frontend/app/src/shared/components/form/utils/mutations/__tests__/`.
- [x] T012 [P] [US1] Vitest for `PoolPrefixLengthInput`: renders only when a pool is selected and pool kind is an IP pool (hidden when no pool selected and for the number-pool path); `prefixlen` resets when the pool changes and is discarded when the pool is cleared (FR-009/FR-010). Cover the attribute host (`input.field`) and a relationship host.
- [ ] T013 [US1] E2E honoring proof. NOTE: the existing `ip-address-create-with-pool.spec.ts` exercises the **attribute** path (the "Address" field), which does not honor `prefixlen` until Slice B (backend) — so a custom-mask assertion there must wait for Slice B. The frontend-only MVP honoring proof should instead be a **relationship-path** e2e (e.g. a device Primary IP Address allocated from a pool with a custom length on a fresh branch, asserting the allocated mask). Author + run against the Playwright stack.

**Checkpoint**: MVP shippable — custom length works for IP-address-from-pool; demoable in the preview.

---

## Phase 4: User Story 1 (cont.) — Extend to prefix + attribute entry points (Priority: P1)

**Goal**: Honor a custom `prefixlen` on the IP-prefix relationship path and the IPAM-native `prefix`/`address` attribute path (FR-011). Requires a GraphQL inline-input change.

**Independent Test**: Create an `IpamIPPrefix` from a prefix pool with length `/28`, save, and confirm a `/28` is created.

- [ ] T014 [US1] Obtain maintainer sign-off for the GraphQL inline-input change (constitution: Ask First — GraphQL schema modifications). **BLOCKER for T015–T017.**
- [ ] T015 [US1] Add `prefixlen: Int` to `IPPrefixPoolInput` and expose `prefixlen` on the IP attribute inline pool input in `backend/infrahub/graphql/types/attribute.py` (leave `size` untouched).
- [ ] T016 [US1] Thread the caller `prefixlen` from the attribute `from_pool` into the IP pool `get_resource` in `backend/infrahub/core/node/__init__.py`, per T003 findings.
- [ ] T017 [US1] Regenerate GraphQL/schema + frontend types (`uv run invoke schema.generate-graphqlschema`; `cd frontend/app && pnpm codegen`) and commit the generated files; never hand-edit them.
- [ ] T018 [P] [US1] Backend functional tests in `backend/tests/component/graphql/resource_manager/`: inline `from_pool` with `prefixlen` allocates at the requested length for IP-address relationship (exists), IP-prefix relationship, and IP `prefix`/`address` attribute; omitting `prefixlen` uses the pool default.
- [ ] T019 [US1] Extend `frontend/app/tests/e2e/ipam/ip-prefix-create-with-pool.spec.ts` for a custom prefix length.

**Checkpoint**: custom length works across all from-pool entry points for IP prefixes and addresses.

---

## Phase 5: User Story 2 — Keep the pool default as the zero-effort path (Priority: P1)

**Goal**: Leaving the control empty allocates at the pool default exactly as today, and the default is communicated to the user.

**Independent Test**: Select a pool, leave the control empty, save, and confirm the allocation matches the pool default and pre-feature behavior.

- [ ] T020 [US2] In `frontend/app/src/shared/components/form/pool-prefix-length-input.tsx`, render placeholder + helper from `defaultPrefixLength` (`empty = pool default (/24)`); neutral placeholder + `empty = pool default` when the default is unknown; ensure empty input omits `prefixlen`.
- [ ] T021 [P] [US2] Vitest: empty value omits `prefixlen`; placeholder reflects the default; neutral fallback when default missing.
- [ ] T022 [US2] E2E regression (address + prefix specs): saving with an empty length reproduces the pre-feature default allocation.

**Checkpoint**: default path verified non-regressed and self-explanatory.

---

## Phase 6: User Story 3 — Prevent invalid prefix lengths (Priority: P2)

**Goal**: Invalid entries are caught inline before submit; valid-but-unsatisfiable requests surface the backend error without losing input.

**Independent Test**: Enter `129` (or `33` for a v4 pool) → inline error and Save blocked; enter a length the pool can't satisfy → Save submits, backend error shown inline, input preserved.

- [ ] T023 [US3] Add client-side validation in `frontend/app/src/shared/components/form/pool-prefix-length-input.tsx` (or the host field error mechanism): integer only; range by family (0–32 v4 / 0–128 v6; 0–128 when family unknown); inline error; block submit (FR-007/FR-008).
- [ ] T024 [US3] Surface the backend allocation error inline when a valid length is unsatisfiable, preserving the pool selection and entered length (FR-013); no client-side capacity pre-check.
- [ ] T025 [P] [US3] Vitest: range validation per family and unknown family; non-integer rejected.
- [ ] T026 [P] [US3] E2E: out-of-range blocks save; unsatisfiable length shows the backend error and preserves input.

**Checkpoint**: validation and error handling complete.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T027 [P] Run `cd frontend/app && pnpm biome:fix` and `uv run invoke format lint`; resolve type issues (no `any`, no non-null assertions).
- [ ] T028 [P] Update from-pool allocation docs under `docs/` if the flow is documented; otherwise record "no doc change" in the PR.
- [ ] T029 Run `/pre-ci` (incl. generated-file/doc validation) and confirm green before pushing. Do not commit the ~24 unrelated working-tree files.

---

## Dependencies

- **Setup** (T001–T002): independent, anytime.
- **Foundational** (T003–T006): T004→(T007–T010); T005→T006; T003→(T015–T016). Must precede story work.
- **US1 MVP** (Phase 3, T007–T013): depends on T004–T006. **Independently shippable.**
- **US1 cont.** (Phase 4): T014 gates T015–T017; T015–T016→T017→T018–T019. Depends on T003.
- **US2** (Phase 5): depends on T007 + T020 (control + default hint).
- **US3** (Phase 6): depends on T007 (control exists).
- **Polish** (Phase 7): after the stories being shipped.

## Parallel execution examples

- Setup: T001 ‖ T002.
- Foundational: T005 ‖ T004 (different files); T006 after T005.
- US1: T011 ‖ T012 (test files); after T007–T010.
- US1 cont.: T018 ‖ T019 (after T015–T017).
- Polish: T027 ‖ T028.

## Implementation strategy

- **MVP**: Phase 1 + Phase 2 (frontend foundational) + Phase 3 (US1 IP-address relationship path). Fully demoable in the preview, zero backend change.
- **Increment 2**: Phase 4 (backend enablement for prefix + attribute paths) once T014 sign-off is obtained.
- **Increment 3**: Phase 5 (default-path guarantees) + Phase 6 (validation/error handling).
- **Finish**: Phase 7 polish + `/pre-ci`.
