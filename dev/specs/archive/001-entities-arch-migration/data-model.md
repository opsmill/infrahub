# Phase 1 Data Model: Layer & Folder Model

This feature's "data model" is structural — the layers, the folders that realize them, and the
files that live in each. There is no runtime schema change.

## Layers

| Layer | Folder | Nesting | Responsibility | May import | Must NOT import |
|-------|--------|---------|----------------|------------|-----------------|
| **API** | `<entity>/api/` | Flat | GraphQL/REST fetchers, clients, generated↔domain mappers. Returns domain types. | `shared/`, own `domain/model` (type-only), generated types | `domain/rules`, `domain/use-cases`, `ui/`, other entities |
| **Domain — model** | `<entity>/domain/model/` | Flat | Domain vocabulary: types, IDs, value objects, filters, sorts, inputs, results. | `shared/` (types), other entities' `domain/model` | `api/`, `domain/rules`, `domain/use-cases`, `ui/`, generated types (pure leaf) |
| **Domain — rules** | `<entity>/domain/rules/` | Flat | Pure business/domain functions, no I-O. | own `domain/model`, `shared/` | `api/`, `ui/`, React, TanStack, Apollo, storage, toast, generated types |
| **Domain — use-cases** | `<entity>/domain/use-cases/` | Flat | Orchestration; calls own `api/`. | own `api/`, own `domain/model`, own `domain/rules`, `shared/` | `ui/`, React, TanStack, Apollo, storage, toast, generated types |
| **UI** | `<entity>/ui/` | Nested (`queries/`, `hooks/`, per-component) | React components, hooks, TanStack query options/mutations, view models, UI state. | own `domain/`, `shared/`, other entities' `domain/` + `ui/` | another entity's `api/` |

**Split rule**: `domain/` uses the `model/`+`rules/`+`use-cases/` split only when it holds >4 files.
No subfolder is created for fewer than 2 files. Below the threshold, `domain/` stays flat with its
current file names.

## File classification heuristic

| A file that… | Goes to |
|---|---|
| declares only types/interfaces/enums (domain vocabulary) | `domain/model/` |
| is a pure function with no fetch/mutation/I-O (`get-decision-options`, `get-schema-hash`, `add-enum`) | `domain/rules/` |
| fetches or mutates via `api/` / orchestrates (`get-branches`, `create-branch`, `load-schema`) | `domain/use-cases/` |
| maps a generated wire shape ↔ a domain type | `api/` |
| is a React component/hook, query-options factory, or view model | `ui/` (in the appropriate subfolder) |

## Per-entity migration record (to be filled during rollout)

| Entity | Domain files (today) | Split? (>4) | Notes |
|--------|----------------------|-------------|-------|
| `role-manager` | 2 | No (flat) | `get-decision-options` → rules classification; validates mechanics + guard. |
| `branches` | 11 | Yes | `branch.mappers.ts` splits: types → `model/`, mapping → `api/`. Fixes generated-leak. Update knowledge doc after. Deferred: `store`/`branchesState` read. |
| `config` | 2 | No (flat) | No `api/` beyond existing; stays flat. |
| `proposed-changes` | 8 | Yes | `proposed-change.types.ts` → `model/`; `get-*-available-actions` likely a rule. |
| `schema` | 8 | Yes | `get-schema-hash`, `add-/remove-enum/dropdown` likely rules; `get-/load-schema` use-cases. |
| _(remaining ~19, incl. `nodes/*` last)_ | — | per policy | Filled per PR. |

## Invariants (must hold after every PR)

1. No file under any migrated `<entity>/domain/**` imports a generated GraphQL/REST type.
2. `domain/model` imports nothing from `api/`, `rules/`, `use-cases/`, or `ui/`.
3. `api/` imports nothing from `domain/rules`, `domain/use-cases`, or `ui/`.
4. The dependency graph is acyclic.
5. Public behavior and existing tests are unchanged (tests move with their subjects).
