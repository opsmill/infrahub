---
description: "Task list for peer-derived parent/children relationship labels"
---

# Tasks: Peer-derived labels for hierarchical parent/children relationships

**Input**: Design documents from `specs/003-parent-children-labels/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — constitution IV mandates a Vitest unit test for the rule and a Playwright E2E for the user-facing behavior. TDD ordering: the rule's unit test is written and failing before the rule is implemented.

**Organization**: One P1 user story. All paths are under `frontend/app/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[US1]**: the single user story

---

## Phase 1: Setup / Verification

**Purpose**: De-risk the discriminator before wiring nine sites to it (critique finding E3).

- [ ] T001 Verify that `relationshipSchema.hierarchical` is truthy on **both** the serialized `parent` and `children` auto-relationships. Inspect the generated type `frontend/app/src/shared/api/rest/types.generated.ts` (RelationshipSchema.hierarchical) and a real/loaded schema (e.g. via the running app or a fixture in `frontend/app/tests/fake/schema.ts`). If only one relationship carries it, record in `specs/003-parent-children-labels/research.md` that the discriminator must also match relationship `kind`/`name` for the other, and adjust T003 accordingly.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: The shared pure rule that every render site depends on.

**⚠️ CRITICAL**: No call-site task (Phase 3) can begin until T003 is complete.

- [ ] T002 [P] Write the failing Vitest unit test in `frontend/app/src/entities/schema/domain/rules/get-relationship-display-label.test.ts` covering contract cases C1–C4 (see `specs/003-parent-children-labels/contracts/get-relationship-display-label.md`): (C1) hierarchical + peer label → peer label; (C2) hierarchical + missing peer/label → `label ?? name`; (C3) non-hierarchical incl. a rel named `parent` → unchanged; (C4) children (cardinality "many") + hierarchical → peer label verbatim (no pluralization). Use `generateRelationshipSchema`/`generateNodeSchema` from `frontend/app/tests/fake/schema.ts`; pass the peer schema as an argument (no store mock). Confirm it FAILS before T003.
- [ ] T003 Implement the pure rule `getRelationshipDisplayLabel(relationshipSchema, peerSchema?)` in `frontend/app/src/entities/schema/domain/rules/get-relationship-display-label.ts` per data-model.md: return `peerSchema.label` when `relationshipSchema.hierarchical` is truthy and `peerSchema?.label` present, else `relationshipSchema.label ?? relationshipSchema.name`. No store access, no side effects. Make T002 pass.

**Checkpoint**: Rule exists, unit-tested, and importable.

---

## Phase 3: User Story 1 — Parent/children labels reflect the peer kind (Priority: P1) 🎯 MVP

**Goal**: Every relationship-label render site shows the peer kind's label for hierarchical parent/children relationships instead of "Parent"/"Children".

**Independent Test**: Open a hierarchical object whose parent/children peers have labels (Location `Region`→`Site`) and confirm each of the five surfaces shows the peer label; confirm a non-hierarchical relationship is unchanged.

> Sites D, E, F, G, H already resolve the peer schema locally — pass it straight into the rule. Sites A, B, C, I must add a `useSchema(relationshipSchema.peer)` lookup and pass the result in.

- [ ] T004 [P] [US1] Route the label through `getRelationshipDisplayLabel` in `frontend/app/src/entities/nodes/object/ui/object-details/object-data-display/object-data-row.tsx` (line ~23). Add `useSchema(fieldSchema.peer)` for the relationship branch (guarded by `"peer" in fieldSchema`) and pass the peer schema in.
- [ ] T005 [P] [US1] Route the metadata-tooltip header through the rule in `frontend/app/src/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row.tsx` (line ~99). Add `useSchema(relationshipSchema.peer)`.
- [ ] T006 [P] [US1] Route the relationship tab label through the rule in `frontend/app/src/entities/nodes/object/ui/object-tabs.tsx` (line ~33). Add `useSchema(relationshipSchema.peer)`.
- [ ] T007 [P] [US1] Route the IPAM tab label through the rule in `frontend/app/src/entities/nodes/object/ui/object-details/object-details-tab.tsx` (line ~37). Reuse the already-resolved `schema` from `useSchema(relationship.peer)` (line ~30).
- [ ] T008 [P] [US1] Route the column header label through the rule in `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-column-header.tsx` (line ~157). Reuse the already-resolved `peerSchema` (line ~139). Leave the attribute path (line ~213) untouched.
- [ ] T009 [P] [US1] Route the form field label through the rule in `frontend/app/src/shared/components/form/utils/getFormFieldFromRelationship.ts` (`getFieldLabel`, line ~30). Thread the peer schema (resolved at line ~80) into `getFieldLabel`; preserve the existing "Add "/"Remove " prefixes composing over the resolved label.
- [ ] T010 [P] [US1] Route the sort-picker item label through the rule in `frontend/app/src/entities/nodes/sort/ui/add-sort/add-sort-picker.tsx` (line ~56). Reuse the already-resolved `peerSchema` (line ~50).
- [ ] T011 [P] [US1] Route the sortable-field label through the rule in `frontend/app/src/entities/nodes/sort/ui/hooks/use-sortable-fields.ts` (line ~54). Reuse the already-resolved `peerSchema` (lines ~46-51). Leave the attribute path (line ~39) untouched.
- [ ] T012 [P] [US1] Route the filter-form heading through the rule in `frontend/app/src/entities/nodes/object/ui/filters/relationship-filter-form.tsx` (line ~82). Add `useSchema(relationshipSchema.peer)`.
- [ ] T013 [US1] Add a Playwright E2E in `frontend/app/tests/e2e/objects/hierarchical-relationship-label.spec.ts` that navigates to a hierarchical object with **distinct** parent/children peers (Location `Region`→`Site`) and asserts the parent field / children tab render the peer label, not "Parent"/"Children". (Depends on T004, T007 at minimum.)

**Checkpoint**: All five surfaces show the peer label consistently; MVP complete.

---

## Phase 4: Polish & Cross-Cutting

- [ ] T014 [P] Add a Towncrier changelog fragment under `changelog/` (e.g. `+<id>.fixed.md`) describing the label change (constitution — every user-facing change requires a fragment).
- [ ] T015 Run the full local CI gate from `frontend/app`: `pnpm exec biome ci .` && `pnpm knip` && `pnpm exec betterer ci` && `pnpm test`. Fix any failures.
- [ ] T016 Run `specs/003-parent-children-labels/quickstart.md` manual validation (all five surfaces + non-hierarchical regression + self-referential IPAM behavior matches the documented edge case).

---

## Dependencies & Execution Order

- **T001 (Setup)** → informs T003's discriminator. Start immediately.
- **T002 → T003 (Foundational)**: test before implementation; both block Phase 3. T003 also depends on T001's finding.
- **T004–T012 (US1 call sites)**: all depend on T003; independent of each other → fully parallel `[P]` (different files).
- **T013 (E2E)**: depends on the call sites it exercises (T004, T007).
- **T014 [P]**: independent, can run any time after T003.
- **T015 / T016**: after all implementation tasks.

### Parallel Opportunities

- T004–T012 can all run in parallel once T003 lands (nine distinct files, no shared edits).
- T002 and T001 can overlap (T001 is inspection; T002 is a new test file).
- T014 can run alongside the call-site tasks.

## Implementation Strategy

MVP = Phases 1–3. Wire the rule (T002/T003) after confirming the discriminator (T001), fan out the nine call-site edits in parallel (T004–T012), prove it with the E2E (T013), then polish (changelog + CI gate + manual validation). No P2/P3 — the derivation is the whole feature.

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- The rule is behaviorally identical to inline `label ?? name` for every non-hierarchical relationship — guarantees SC-002 (zero regression).
- Self-referential hierarchies (IPAM prefixes) intentionally show the same label for parent and children — documented, accepted for v1 (see spec Edge Cases / Assumptions).
