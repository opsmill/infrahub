# Implementation Plan: Number pool create and edit form

**Branch**: `number-pool-form-ifc-3365` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/ifc-3365-number-pool-form/spec.md`

## Summary

Replace the single-range number pool form with a form that creates a pool with its node, number attribute, optional allocation scope and weighted ranges in one save, and edits a pool's name, description and ranges.

- **No backend change:** the backend already accepts `ranges` and `allocation_scope` on `CoreNumberPoolCreate` and `CoreNumberPoolUpdate`.
- **Frontend work:**
  - a new form in the `resource-manager` entity's `ui/` layer;
  - three number pool rules in its `domain/rules/`;
  - one optional setting on the generic `nodes/object` save path, which turns off the global error toast so the form can show backend errors inline;
  - the pool query also loads the stored ranges for edit.
- **Removed:** the old form and the `/proto/number-pool` prototype.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler enabled)

**Primary Dependencies**:
- react-hook-form, through `shared/components/ui/form.tsx`
- `@infrahub/ui` (`Select`, `Autocomplete`, `ListBox`, `Popover`, `Sheet`)
- react-aria-components (`TagGroup`)
- TanStack Query
- json-to-graphql-query

No new dependency.

**Storage**: N/A (backend unchanged)

**Testing**:
- Vitest in browser mode, for the rule unit tests and the form component tests.
- pytest-playwright, for the e2e tests in `tests/e2e/`.

**Target Platform**: Web app (`frontend/app`)

**Project Type**: Web application, frontend only

**Performance Goals**: The node list is built from the schema already loaded in the browser. No request is added while the user fills the form. Edit adds `ranges` to the pool query that the details page already runs.

**Constraints**:
- Range values must be sent as bare integer literals. The form accepts whole numbers up to `Number.MAX_SAFE_INTEGER` (see `research.md`, "Payload typing and number encoding").
- The callers own the `Sheet` and its title.

**Scale/Scope**:
- One new form folder and three domain rules.
- One query extended, and one optional parameter threaded through the generic object create and update.
- Three e2e files and one docs page updated, and the prototype removed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | Pass | No schema change. Node, attribute and scope choices come from the loaded schema. No generated file is edited by hand. |
| II. Branch-Safe by Default | Pass, with a known gap | The scope picker uses the current branch's schema, while the backend checks the scope against the default branch's schema. The backend refuses a mismatch on save. The spec records this as a known limitation. |
| III. Type Safety & Explicit Contracts | Pass | The payload is typed as the generated `CoreNumberPoolCreateInput` and `CoreNumberPoolUpdateInput`, with `BigInt` mapped to `number` in codegen and gql.tada (`research.md`, "Payload typing and number encoding"). No `any`, and no `as` or `!` assertions. |
| IV. Test Discipline | Pass | Unit tests for the three rules. Component tests for the form. A unit test for the toast setting. E2E tests for the P1 and P2 scenarios, extending the existing number pool spec. |
| V. Query Performance | Pass | One query gains `ranges`. No N+1 pattern. |
| VI. Security & Input Boundaries | Pass | The backend stays the final check for every rule. The browser repeats two checks only to give early feedback. Permissions are unchanged. |
| VII. Simplicity & Maintainability | Pass, with a justified exception | The generic save path is reused instead of adding number pool fetchers. Two backend rules are repeated in the browser (see Complexity Tracking). |

**Quality gates**: format and lint, `pnpm knip`, `betterer ci`, a changelog fragment, and the user doc updated.

**Post-design re-check**: unchanged. The design adds no dependency, no schema change and no API change.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3365-number-pool-form/
├── spec.md
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── number-pool-form.md
├── checklists/
│   └── requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code

```text
frontend/app/src/
├── entities/resource-manager/
│   ├── api/
│   │   ├── get-number-pool-from-api.ts       # changed: GET_NUMBER_POOL also requests ranges
│   │   └── number-pool.mappers.ts            # changed: maps ranges, with weight as number | null
│   ├── domain/
│   │   ├── model/number-pool.ts              # changed: NumberPoolData.ranges
│   │   └── rules/
│   │       ├── can-number-pool-allocate-to.ts   # new
│   │       ├── can-number-pool-be-scoped-by.ts  # new
│   │       └── find-overlapping-ranges.ts    # new
│   └── ui/
│       ├── number-pool-form.tsx              # deleted (old single-range form)
│       └── number-pool/
│           ├── details/                      # moved: the existing details page components and their tests, unchanged
│           │   ├── number-pool-actions-menu.tsx
│           │   ├── number-pool-allocation-filters-bar.tsx
│           │   ├── number-pool-allocations-card.tsx
│           │   ├── number-pool-allocations-table.tsx
│           │   ├── number-pool-header.tsx
│           │   ├── number-pool-ranges-card.tsx
│           │   └── number-pool-usage-bar.tsx
│           └── form/                         # new
│               ├── number-pool-form.tsx                    # NumberPoolForm — the form and its inputs, given a form instance, a submit handler and isAllocatesReadOnly; no state
│               ├── number-pool-create-form.tsx             # NumberPoolCreateForm — wraps NumberPoolForm: useForm, create mutation, "created" toast
│               ├── number-pool-edit-form.tsx               # NumberPoolEditForm — wraps NumberPoolForm: loads the pool, useForm({ values }), update mutation, "updated" toast, read-only "What it allocates"
│               ├── number-pool-form-values.ts              # form value type, field rules, payload conversion
│               ├── number-pool-allocates-input.tsx         # NumberPoolAllocatesInput — "What it allocates", reveal layout; isReadOnly in edit
│               ├── number-pool-node-select.tsx             # NumberPoolNodeSelect → node
│               ├── number-pool-node-attribute-select.tsx   # NumberPoolNodeAttributeSelect → node_attribute
│               ├── number-pool-allocation-scope-select.tsx # NumberPoolAllocationScopeSelect → allocation_scope
│               └── number-pool-ranges-input.tsx            # NumberPoolRangesInput → ranges
├── entities/nodes/object/
│   ├── api/{create,update}-object-from-api.ts        # changed: optional toast setting on the request context
│   ├── domain/use-cases/{create,update}-object.ts    # changed: pass the setting through
│   └── ui/queries/{create,update}-object.mutation.ts # changed: pass the setting through
├── shared/components/form/object-form.tsx  # changed: routes CoreNumberPool to NumberPoolCreateForm or NumberPoolEditForm
├── pages/resource-manager/number-pool-details{,.test}.tsx  # changed: import paths only (number-pool/details/)
├── pages/proto/number-pool/                # deleted
└── app/router.tsx                          # changed: /proto/number-pool route removed

tests/e2e/
├── resource-manager/test_number_pool.py              # changed: new labels, P1 and P2 scenarios
├── object-template/test_template_with_number_pool.py # changed: new labels
└── tutorial/guides/test_resource_manager_guide.py    # changed: new labels, docs screenshot

docs/docs/resource-manager/allocate-number.mdx  # changed: ranges, weights and scope
changelog/+ifc-3365-number-pool-form.changed.md # new
```

**Structure Decision**:
- **Frontend only.** The form is `ui/` code in the `resource-manager` entity, and its `domain/` layer gains only number pool rules and one vocabulary type.
- **Saving** goes through the generic object mutations of `nodes/object`. `resource-manager/ui` may call another entity's `ui/queries`.
- **Form logic stays in `ui/`:** form values, parsing, validation, field dependencies and display.
- **`ui/number-pool/` is split into `details/` and `form/`,** so the details page components and the form components can each be scanned on their own. The existing components move to `details/` without any code change. Only their import paths change.
- **The edit form's ranges come from the resource manager's pool query.** The generic edit query does not load component relationships.

## Implementation order

1. **Move** the existing number pool components and their tests to `ui/number-pool/details/`, and update the imports. The tests must pass with no other change. Do this as its own commit, so the move is reviewed apart from new code.
2. **Toast setting** on the generic object create and update, with a unit test.
3. **Domain rules** `canNumberPoolAllocateTo`, `canNumberPoolBeScopedBy` and `findOverlappingRanges`, with unit tests.
4. **Pool query** loads `ranges`, with mapper tests: a stored empty weight maps to `null`.
5. **Form components** in `ui/number-pool/form/` for the create flow, with component tests. Then switch `object-form.tsx` to the new form, and remove the old form.
6. **Edit flow:** `NumberPoolAllocatesInput` with `isReadOnly`, and ranges loaded from the pool query, with component tests.
7. **E2E tests**: new labels, plus the P1 and P2 scenarios.
8. **Remove** the prototype and its route. Revert the `mock-unscoped` edits.
9. **Docs page** and changelog fragment.

## Complexity Tracking

| Exception | Why needed | Simpler alternative rejected because |
|---|---|---|
| `canNumberPoolBeScopedBy` repeats the backend's per-field scope rules (`backend/infrahub/pools/scope.py::AllocationScopeValidator.check_element`). The entity guide's "Backend is authoritative" rule forbids a client-side copy of a server rule. | FR-006: the picker hides fields the backend would refuse. No API lists the fields that can scope a pool. | Showing every field and letting the backend refuse it on save was rejected by the user. Adding an API that lists usable fields would be a GraphQL change, which this feature avoids. The backend still makes the final check, so a drift causes a refused save, not bad data. |
| `findOverlappingRanges` repeats the backend's overlap check (`backend/infrahub/pools/number_pool_range_validation.py`). | FR-011: overlaps are flagged on both rows before sending. The backend reports only the lowest failing range, by its bounds. | Leaving overlap to the backend was rejected by the user. The backend stays the final check. |
