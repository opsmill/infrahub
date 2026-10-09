# Implementation Plan: Number attribute — set a number or take it from a number pool

**Branch**: `ple-number-pool-field-ifc-3371` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3371-number-pool-field-tabs/spec.md`

## Summary

The Number field already renders the value-or-pool tabs (`PoolBackedField`) when a number pool
targets the attribute, but its pool tab has no number input and the save sends `from_pool` alone.
This plan adds a number input to the pool tab for number pools, changes the create and update
payloads so the form always sends `value` with `from_pool` (attach when a number is given,
`value: null` to allocate), sends `from_pool: null` when the user leaves a pool-tracked number for
the Value tab, and opens the edit form on the pool tab when a pool tracks the attribute. No backend
change: the backend contract is
[`from-pool-intent.md`](../ifc-3184-pool-number-attach/contracts/from-pool-intent.md) on
`feature-number-pools-1.12`.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler on: no manual memoization)

**Primary Dependencies**: react-hook-form (existing form state), existing `@/shared/components/form`
pool components, generated GraphQL types

**Storage**: N/A (frontend only)

**Testing**: Vitest unit tests for the payload builders and default-value logic; Vitest browser
component tests for the field; pytest-playwright e2e in `tests/e2e/resource-manager/`

**Target Platform**: Infrahub web UI

**Project Type**: Web application, frontend slice only

**Performance Goals**: No new request. The number pools are already fetched once per form by
`useGetNumberPools` in `shared/components/form/node-form.tsx`.

**Constraints**: Must reuse `PoolBackedField` and `PoolAllocationPanel`, not copy them
(IFC-2764 FR-008). Must not change IP field behaviour.

**Scale/Scope**: About 8 source files under `frontend/app/src/shared/components/form/` and
`frontend/app/src/shared/components/inputs/`, their unit tests, and one e2e file.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Schema-Driven Integrity | Pass | Field availability is still derived from the schema and the pools that target the kind and attribute. |
| II. Branch-Safe by Default | Pass | Mutations already carry the branch context; nothing new. |
| III. Type Safety & Explicit Contracts | Pass | The staged number is added to the typed `AttributeValueFromPool`; the submission table is written as a contract ([contracts/form-submission.md](contracts/form-submission.md)). |
| IV. Test Discipline | Pass | Unit tests per row of the submission table; e2e test extended for attach, allocate and edit. |
| V. Query Performance | Pass | No new query. |
| VI. Security & Input Boundaries | Pass | The backend validates the pool and the number; the form only checks that a number is an integer. |
| VII. Simplicity | Pass | Extends the existing override pattern (nested field under `value.from_pool`) instead of adding a new field type. |

Re-check after Phase 1 design: unchanged, all pass.

## Design

### D1. Staged number lives on the pool value

`AttributeValueFromPool.value.from_pool` gains an optional `number?: number | null`, registered as
the nested form field `<name>.value.from_pool.number`, the same way the IP prefix-length override
registers `<name>.value.from_pool.prefixLength` (`shared/components/inputs/pool-select.tsx::PoolPrefixLengthField`).
A new `PoolNumberField` in the same file renders it only when the pool kind is `CoreNumberPool`
and the field is not template-backed. `PoolAllocationPanel` renders it below the pool picker.

### D2. Payload builders always pair `from_pool` with `value`

`shared/components/form/utils/mutations/buildFromPoolMutationValue.ts` gains a helper that, for a
number pool, returns `{ value: number ?? null, from_pool: { id } }`. Both
`getCreateMutationFromFormData` and `getUpdateMutationFromFormData` use it in their `pool` branch
when the field has no `fromPoolRelationshipName`. The template path is untouched.

### D3. Leaving a tracked number sends `from_pool: null`

In `getUpdateMutationFromFormData`, the `user` branch adds `from_pool: null` to the attribute
payload when the field is a Number attribute, has no `fromPoolRelationshipName`, and its
`defaultValue.source.type === "pool"`. Row 13 of the backend table: detach, number unchanged or
replaced by the typed one.

### D4. Edit form shows the tracked state in the pool tab

`shared/components/form/utils/getFieldDefaultValue.ts::getDefaultValueFromPool` builds, for a
`CoreNumberPool` source, `{ source: <pool>, value: { from_pool: { id, number: <current number> } } }`
instead of casting the raw number into the `from_pool` shape. `PoolBackedField` gains an
`initialTab` derived by the caller: `NumberField` passes the pool tab when
`defaultValue.source.type === "pool"` and the pool kind is `CoreNumberPool`. IP fields keep the
value tab (IFC-2764 FR-017).

### D5. Unchanged-field detection covers the number

The early return in `getUpdateMutationFromFormData` for "same pool as the default" compares the
staged `number` with the default's `number` for number pools, so a changed number on the same
pool is sent (row 3) and an unchanged one is not.

### D6. Picking a pool pre-fills the number the node holds

When the user picks a pool, `NumberField` pre-fills `number` with, in order: the number already
staged in the pool tab, else the number the node holds when the default source is the user or a
pool (edit form). It is left empty for a schema default, a profile or a template, so a create
form allocates by default. This makes "pick pool B and keep the number" (spec US4.4, US4.9) need
no retyping, and avoids allocating a new number over an existing node by accident. Re-picking the
original pool restores the default as today.

### D7. Validation in the pool tab

The pool tab requires a pool when a number is typed (FR-014): a `validate` rule on the host field
returns "Select a pool, or use the Value tab for a number without a pool" when the staged value
has a number and no pool. The number input accepts whole numbers only; no range check
(contract, FR-029 deleted).

Full row-by-row behaviour: [contracts/form-submission.md](contracts/form-submission.md).
Decisions and rejected options: [research.md](research.md).

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3371-number-pool-field-tabs/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── form-submission.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
frontend/app/src/shared/components/
├── form/
│   ├── type.ts                                   # AttributeValueFromPool.from_pool.number
│   ├── pool-backed-field.tsx                     # initialTab prop
│   ├── pool-allocation-panel.tsx                 # renders PoolNumberField
│   ├── fields/number.field.tsx                   # initialTab, keep number on pool change
│   ├── fields/number.field.test.tsx
│   └── utils/
│       ├── getFieldDefaultValue.ts               # number-pool default value shape
│       ├── getFieldDefaultValue.test.ts
│       ├── updateFormFieldValue.ts               # carry number on pool change
│       └── mutations/
│           ├── buildFromPoolMutationValue.ts     # value + from_pool for number pools
│           ├── getCreateMutationFromFormData.ts
│           ├── getCreateMutationFromFormData.test.ts
│           ├── getUpdateMutationFromFormData.ts  # detach, same-pool number compare
│           └── getUpdateMutationFromFormData.test.ts
└── inputs/pool-select.tsx                        # PoolNumberField
tests/e2e/resource-manager/test_number_pool.py    # attach, allocate, edit, detach
changelog/                                        # towncrier fragment
```

**Structure Decision**: Frontend-only change inside the existing shared form module; no new
directory.

## Complexity Tracking

No constitution violation.
