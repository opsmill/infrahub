# Implementation Plan: Column-Header Sort & Filter Menu

**Branch**: `header-sort-menu-ifc-2794` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-header-sort-menu/spec.md`

## Summary

Replace the object table's header filter popover with a column-header **menu** offering "Sort ascending", "Sort descending" (attribute columns), a "Sort by ▸" peer-attribute submenu (cardinality-one relationship columns), and "Filter…" (opens the existing per-column filter form). Header-applied sorts replace the whole sort with a single-field sort, share state with the toolbar SortPicker through the existing `useSort` hook and `?sort=` URL param, and toggle-clear back to the schema default order. The IPAM IP-address/IP-prefix tables reuse the same header component but currently lack sort plumbing — that wiring (order argument through use-case → API) is added as a final phase.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler enabled — no manual `useMemo`/`useCallback`)

**Primary Dependencies**: Vite 8.0, TanStack Table (`manualSorting: true`, server-side), TanStack Query, nuqs (URL state), `@infrahub/ui` (react-aria-components Menu/Popover), Tailwind CSS 4.2

**Storage**: N/A — all state in URL query params (`?sort=`, `?filters=`) via nuqs; server-side ordering via existing GraphQL `OrderInput`

**Testing**: Vitest 4.1 browser mode (playwright provider, `tests/components/render.tsx` helper) for component tests; Playwright 1.60 for E2E (`frontend/app/tests/e2e/objects/`)

**Target Platform**: Web (Infrahub frontend SPA)

**Project Type**: Web application — frontend only; zero backend/API/schema changes

**Performance Goals**: No additional list refetches beyond one reload per sort change (SC-004); no client-side sorting introduced

**Constraints**: Must not regress any existing filtering behavior (SC-003); header and toolbar sort UIs must never disagree (FR-007); sort input from headers must pass the existing `getValidSorts` allowlist (FR-009)

**Scale/Scope**: 3 user stories; ~1 reworked component (`TableColumnHeader`), ~2 new UI helpers, IPAM sort wiring across 2 entity paths (~6 files), component tests + 2 E2E specs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| I. Schema-Driven Integrity | No schema, generated-file, or data-structure changes. Generated GraphQL types (`OrderInput`) consumed read-only. | ✅ Pass |
| II. Branch-Safe by Default | Frontend-only; reuses existing branch-aware list queries unchanged. Sorting is an argument to existing queries. | ✅ Pass |
| III. Type Safety & Explicit Contracts | TS strict; existing `Sort`/`SortField` domain types reused; no `any`, no assertions planned. | ✅ Pass |
| IV. Test Discipline | Vitest browser component tests for the header menu (colocated, GIVEN/WHEN/THEN); Playwright E2E for header sort on object lists and IPAM. Feature not complete until E2E passes. | ✅ Pass (planned) |
| V. Query Performance & Efficiency | Server-side ordering via existing `order: {by: [...]}` argument; no new query shapes, no N+1. | ✅ Pass |
| VI. Security & Input Boundaries | Header-emitted sorts flow through `getValidSorts` allowlist exactly like URL-sourced sorts (FR-009). No new input surface reaches GraphQL unvalidated. | ✅ Pass |
| VII. Simplicity & Maintainability | Reuses `useSort`, `useFilters`, existing filter forms, existing sort domain rules, and the canonical `@infrahub/ui` Menu+SubmenuTrigger pattern from `add-sort-picker.tsx`. No new dependencies, no new state stores. | ✅ Pass |

**Post-design re-check (after Phase 1)**: unchanged — all gates still pass. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/002-header-sort-menu/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── header-menu-ui.md  # UI + URL-state contract
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/app/src/
├── entities/nodes/object/ui/object-table/
│   ├── cells/
│   │   ├── table-column-header.tsx        # REWORK: Radix filter popover → react-aria menu (sort + filter)
│   │   ├── table-column-header.test.tsx   # NEW: vitest browser component tests
│   │   └── table-column-header-simple.tsx # unchanged (plain header, used where non-interactive)
│   └── utils/get-object-table-columns.tsx # touch only if header props change
├── entities/nodes/sort/
│   ├── domain/
│   │   ├── model/sort.ts                  # existing Sort/SortField — reused, unchanged
│   │   └── rules/                         # existing: is-sortable-attribute, is-sortable-relationship,
│   │                                      #   sort-field builders, get-valid-sorts — reused
│   │                                      # NEW rule if needed: is-column-sort-active (field ↔ column match)
│   └── ui/
│       ├── hooks/use-sort.ts              # existing — single source of sort state (unchanged or minimal)
│       └── add-sort/add-sort-picker.tsx   # pattern donor for Menu + SubmenuTrigger (unchanged)
├── entities/ipam/
│   ├── ip-addresses/
│   │   ├── api/get-ip-address-list-from-api.ts   # ADD: order arg via addOrderByToRequest
│   │   ├── domain/use-cases/get-ip-address-list.ts # ADD: sort param
│   │   └── ui/ (query hook + ip-address-table.tsx)  # ADD: useSort wiring
│   └── ip-prefixes/                                # same three-layer additions
└── shared/api/graphql/utils.ts            # existing addOrderByToRequest — reused

frontend/app/tests/e2e/
├── objects/object-header-sort.spec.ts     # NEW: header sort E2E (object list)
└── ipam/ip-prefix-list-sort.spec.ts       # NEW: IPAM header sort E2E
```

**Structure Decision**: Follows the established entities three-layer architecture (`api/` → `domain/` → `ui/`). The feature is concentrated in the shared `TableColumnHeader` cell component; sorting logic stays in the existing `sort` entity's domain layer; IPAM gains the same `sort` parameter plumbing the object list already has. No new entities, no new folders beyond test files.

## Phase 0: Research — see [research.md](./research.md)

All Technical Context unknowns resolved; key decisions:

1. **Menu primitives**: `@infrahub/ui` react-aria `MenuTrigger`/`Menu`/`MenuItem`/`SubmenuTrigger`, copying the canonical two-level pattern from `add-sort/add-sort-picker.tsx` + `add-sort-button.tsx`. The Radix popover in `table-column-header.tsx` is replaced.
2. **Filter… mechanics**: menu action closes the menu, then opens a controlled react-aria Popover anchored to the header containing the existing `AttributeFilterForm`/`RelationshipFilterForm` (unchanged forms, `onSuccess` closes).
3. **Sort semantics**: "Sort asc/desc" → `setCustomSort([{field, direction}])` (full replace). Toggle-clear: selecting the active direction again → `setCustomSort(null)` (URL param removed, schema default restored). Field strings via existing `buildAttributeSortField` / `buildRelationshipSortField`.
4. **IPAM wiring is missing** (verified): no `order` arg, no `useSort` on IPAM paths. Added as final phase — additive, mirrors `get-objects-from-api.ts:51`. **Release-blocking** (spec assumption updated per critique X1): the shared header must not ship dead sort entries on IPAM tables.
5. **Changelog**: a Towncrier fragment in `changelog/` describing the new header menu and the changed filter interaction (menu → "Filter…" instead of direct popover) is a required deliverable (Constitution quality gate 5, critique E8).

## Phase 1: Design & Contracts

- **[data-model.md](./data-model.md)** — existing `Sort`/`SortField`/token model (unchanged) + the derived per-column header capability model (sort entries, submenu entries, active state).
- **[contracts/header-menu-ui.md](./contracts/header-menu-ui.md)** — the header menu UI contract per column type, URL-state contract (`?sort=` tokens), and shared-state invariants with the toolbar SortPicker.
- **[quickstart.md](./quickstart.md)** — runnable validation guide (dev server scenarios, component test and E2E commands).
- **Agent context**: root `CLAUDE.md`/`AGENTS.md` carry no `<!-- SPECKIT -->` markers; the plan reference is tracked via `.specify/feature.json` (already pointing at this feature directory). No agent context file edit required.

## Complexity Tracking

No constitution violations — table intentionally left empty.
