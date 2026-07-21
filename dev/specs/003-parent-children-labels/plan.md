# Implementation Plan: Peer-derived labels for hierarchical parent/children relationships

**Branch**: `parent-children-labels-ifc-2930` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-parent-children-labels/spec.md`

## Summary

For hierarchical objects, replace the generic "Parent"/"Children" relationship labels with the **peer kind's own schema label** (e.g. "Region"), everywhere the relationship label is rendered. This is a **frontend-only** change: introduce one pure rule in the schema domain layer, `getRelationshipDisplayLabel(relationshipSchema, peerSchema)`, and route every relationship-label render site through it. The rule detects the hierarchical parent/children relationship via `relationshipSchema.hierarchical` (a field already present on the relationship, set to the hierarchy generic's kind), swaps in `peerSchema.label` when available, and otherwise returns today's `label ?? name`.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2

**Primary Dependencies**: Existing only — jotai schema atoms, `resolveSchema`/`useSchema`/`getSchema`. No new dependencies.

**Storage**: N/A (display-only; reads schema already loaded client-side)

**Testing**: Vitest (unit, browser mode) for the rule; Playwright E2E for the user-facing behavior (constitution IV)

**Target Platform**: Web frontend (`frontend/app`)

**Project Type**: Web application — frontend only for this feature

**Performance Goals**: No measurable impact — peer schema is already resolved from in-memory atoms at most sites

**Constraints**: Frontend-only. No backend, schema, migration, or generated-type change. Must not alter labels of non-hierarchical relationships.

**Scale/Scope**: One new domain rule + one colocated unit test; ~8–9 render call sites updated; one E2E test; one changelog fragment.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| I. Schema-Driven Integrity | **Pass** — no schema change; no generated file edited. Reads existing `RelationshipSchema.hierarchical`/`peer` and node/generic `.label`. |
| II. Branch-Safe by Default | **N/A** — pure display derivation, no DB query, no branch/temporal logic. |
| III. Type Safety & Explicit Contracts | **Pass** — TS, generated OpenAPI types (`RelationshipSchema`, `ModelSchema`), no `any`, no `as`/`!`. |
| IV. Test Discipline | **Pass** — unit test colocated with the rule; Playwright E2E for the user-facing feature (required by IV; feature not complete until E2E passes). |
| V. Query Performance | **N/A** — no queries added. |
| VI. Security & Input Boundaries | **N/A** — no new input boundary. |
| VII. Simplicity & Maintainability | **Pass** — single pure helper serving ~9 callers (well past the ≥2 extraction threshold); no premature abstraction, no new dependency. |

**Governance "Ask First" gates** (from AGENTS.md): none crossed — no DB/schema, no GraphQL/API, no new dependency, no CI/CD, no auth change.

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-parent-children-labels/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── get-relationship-display-label.md   # UI contract for the rule
└── checklists/
    └── requirements.md  # from /speckit-specify
```

### Source Code (repository root)

```text
frontend/app/src/entities/schema/domain/rules/
├── get-relationship-display-label.ts        # NEW — the pure resolver rule
├── get-relationship-display-label.test.ts   # NEW — colocated Vitest unit test
└── is-hierarchical-schema.ts                # existing (reference/adjacent)

frontend/app/src/entities/nodes/object/ui/object-details/object-data-display/
├── object-data-row.tsx                      # Site A — detail row (primary)
└── object-relationship-row.tsx              # Site B — metadata tooltip header

frontend/app/src/entities/nodes/object/ui/
├── object-tabs.tsx                          # Site C — relationship tab label
└── object-details/object-details-tab.tsx    # Site D — IPAM tab label

frontend/app/src/entities/nodes/object/ui/object-table/cells/
└── table-column-header.tsx                  # Site E — sortable relationship column header

frontend/app/src/entities/nodes/sort/ui/
├── add-sort/add-sort-picker.tsx             # Site G — sort picker menu item
└── hooks/use-sortable-fields.ts             # Site H — sortable-fields hook

frontend/app/src/entities/nodes/object/ui/filters/
└── relationship-filter-form.tsx             # Site I — filter form heading

frontend/app/src/shared/components/form/utils/
└── getFormFieldFromRelationship.ts          # Site F — form field label (consistency; optional)

frontend/app/tests/e2e/
└── <hierarchical-object-label>.spec.ts      # NEW — E2E asserting peer label renders

changelog/
└── +<fragment>.fixed.md                     # NEW — Towncrier fragment
```

**Structure Decision**: Frontend-only. The single new unit of logic lives in the schema **domain/rules** layer (matching `is-hierarchical-schema.ts`); every UI site consumes it. No `ui/` concepts leak into the rule and the rule name uses domain vocabulary.
