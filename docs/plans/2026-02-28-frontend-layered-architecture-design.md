# Frontend Layered Architecture Design

## Problem

The frontend codebase has an existing three-layer pattern (api/domain/ui) documented and partially adopted. Adoption is inconsistent: some entities follow it cleanly (branches, artifacts), some have React hooks polluting the domain layer, and others lack layers entirely (groups, role-manager, triggers). The `nodes/object` entity — the largest and most complex — mixes api and domain concerns in a single file.

## Goals

- Clear separation between API transport, business logic, and UI rendering
- Each layer is independently testable and theoretically swappable
- Consistent pattern across all 23 entities
- Zero framework imports (React, TanStack, Jotai) in domain/ or api/

## Architecture

### Layer Structure

```
entities/{name}/
├── api/                              # Transport — raw network calls
│   ├── get-{noun}-from-api.ts        # GraphQL/REST call, returns raw response types
│   └── create-{noun}-from-api.ts
├── domain/                           # Business logic — pure TypeScript
│   ├── {noun}.types.ts               # Domain types (the canonical contract)
│   ├── {noun}.mappers.ts             # OPTIONAL — only when transformation is non-trivial
│   ├── get-{noun}.ts                 # Async function: calls api/, returns domain types
│   └── create-{noun}.ts
└── ui/                               # React — framework integration
    ├── queries/
    │   ├── {noun}.query-keys.ts      # Query key factory
    │   ├── get-{noun}.query.ts       # queryOptions factory + useQuery hook
    │   └── create-{noun}.mutation.ts # useMutation hook + cache invalidation
    ├── hooks/
    │   └── use-{noun}-{thing}.ts     # Entity-specific React hooks
    └── {noun}-table.tsx              # React components
```

### Layer Rules

| Rule | Description |
|------|-------------|
| api/ imports | `shared/api/` only. No React, no domain/, no other entities. |
| domain/ imports | `api/` (same entity), `shared/utils/`, other entities' `domain/` only. No React, no TanStack, no Jotai. |
| ui/ imports | `domain/` (same entity), `shared/`, other entities' `domain/` and `ui/`. React, TanStack, Jotai allowed. |
| Cross-entity | Import from another entity's `domain/` (types, async functions) or `ui/` (hooks, components). Never from another entity's `api/`. |
| Circular deps | No circular dependencies between entities. The dependency graph must be a DAG. |

### Data Flow

```
Page (thin route wrapper)
  └── ui/ component (renders, handles user interaction)
        └── ui/queries/ hook (reads branch/date/schema from context, calls queryOptions)
              └── domain/ async function (calls api, transforms response)
                    └── api/ function (raw network call)
```

Global state (branch, date, schema) is injected at the ui/ layer and passed as parameters to domain/ functions. Domain functions never read global state directly.

### queryOptions and TanStack Query

queryOptions factories and useQuery/useMutation hooks live in `ui/queries/`. Domain's public API is async functions and types only.

Rationale: `queryOptions` configures TanStack Query, a framework choice. Caching strategy, query keys, and reactive subscriptions are UI-layer concerns. A TUI would call domain async functions directly without TanStack.

```ts
// domain/get-branches.ts — pure, no framework imports
export async function getBranches(
  branch: string,
  date?: string,
  filters?: BranchFilters
): Promise<BranchListItem[]> {
  const raw = await getBranchesFromApi(branch, date, filters);
  return raw.CoreBranch.edges.map(mapToBranchListItem);
}

// ui/queries/get-branches.query.ts — React + TanStack integration
export function getBranchesQueryOptions(branch: string, date?: string, filters?: BranchFilters) {
  return queryOptions({
    queryKey: branchKeys.list(branch, date, filters),
    queryFn: () => getBranches(branch, date, filters),
  });
}

export function useGetBranches(filters?: BranchFilters) {
  const branch = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  return useQuery(getBranchesQueryOptions(branch, date, filters));
}
```

### Mappers

Mappers are optional. Use them only when transformation is non-trivial (more than 5-6 lines of field access). For simple or schema-driven entities, inline the transformation in the domain async function.

For `nodes/object`: no mapper file. Domain types (`NodeObject`, `NodeAttribute`, `NodeRelationship`) represent the generic shape. The "mapping" is type narrowing, not reshaping.

### Dynamic Queries (nodes/object)

The dynamic query builder moves to `api/`. It takes schema metadata as input and produces a GraphQL query. Domain functions receive schema as a parameter.

```
nodes/object/
├── api/
│   ├── build-object-query.ts        # schema metadata → GraphQL query string
│   ├── get-objects-from-api.ts      # executes a built query
│   └── get-object-from-api.ts
├── domain/
│   ├── object.types.ts              # NodeObject, NodeAttribute, NodeRelationship
│   └── get-objects.ts               # async fn: calls api, returns domain types
└── ui/
    ├── queries/
    │   ├── object.query-keys.ts
    │   └── get-objects.query.ts     # queryOptions + useGetObjects (injects schema from useSchema)
    └── object-table/
```

### File Naming

| Suffix | Purpose | Location | Example |
|--------|---------|----------|---------|
| `-from-api.ts` | Raw network call | api/ | `get-branches-from-api.ts` |
| `.types.ts` | Domain types | domain/ | `branch.types.ts` |
| `.mappers.ts` | Transform functions (optional) | domain/ | `branch.mappers.ts` |
| `.query-keys.ts` | Query key factory | ui/queries/ | `branch.query-keys.ts` |
| `.query.ts` | queryOptions + useQuery | ui/queries/ | `get-branches.query.ts` |
| `.mutation.ts` | useMutation + cache ops | ui/queries/ | `create-branch.mutation.ts` |

All files use kebab-case. Tests are colocated with source. No barrel `index.ts` files.

### Enforcement

Documentation and code review. The rules are simple enough that lint configuration adds friction without proportional benefit.

## Migration Plan

Full codebase migration across 8 waves, sequenced by dependency order and effort.

### Wave 1 — Foundation (reference implementation)

**Entity:** `branches`
**Goal:** Canonical example of the new pattern. Unblocks all other entities since `useCurrentBranch` is imported everywhere.

Steps:
1. Create `ui/queries/` directory
2. Move queryOptions factories and useQuery hooks from `domain/*.query.ts` to `ui/queries/`
3. Move query key factories from `domain/` to `ui/queries/`
4. Make domain async functions accept branch/date as parameters
5. Verify zero React imports in domain/
6. Update `dev/guidelines/frontend/naming-conventions.md`
7. Update `dev/knowledge/frontend/entities-structure.md`

### Wave 2 — Low effort entities

**Entities:** `artifacts`, `authentication`, `config`, `object-file`, `user-profile`, `generators`
**Effort:** Mechanical — mostly moving `*.query.ts` files from domain/ to ui/queries/.

### Wave 3 — Medium effort entities

**Entities:** `events`, `navigation`, `schema`, `repository`, `resource-manager`, `tasks`, `permission`
**Effort:** Same mechanical move, plus cleanup of legacy directories (e.g., `permission/queries/`).

### Wave 4 — IPAM sub-entities

**Entities:** `ipam/ip-addresses`, `ipam/ip-namespaces`, `ipam/ip-prefixes`, `ipam/ipam-tree`
**Effort:** Batched — shared patterns and utilities across sub-entities.

### Wave 5 — Nodes sub-entities

**Entities:** `nodes/convert`, `nodes/hierarchy`, `nodes/profiles`, `nodes/relationships`
**Effort:** Clean up root-level `nodes/` flat files. Move to appropriate sub-entities or shared.

### Wave 6 — High effort entities

**Entities (1 PR each):**
- `groups` — add domain/ layer, replace direct Apollo usage in ui/
- `role-manager` — add domain/ layer, replace direct Apollo usage in ui/
- `diff` — restructure `checks/` and `node-diff/` under ui/
- `triggers` — add api/ and domain/ layers
- `proposed-changes` — remove legacy Apollo api/ pattern, largest migration

### Wave 7 — nodes/object (dedicated)

**Entity:** `nodes/object` (~75 files)
- Extract dynamic query builder from domain/ to api/
- Make domain functions pure async, accept schema as parameter
- Move queryOptions to ui/queries/
- May be split into multiple PRs

### Wave 8 — Cleanup

- Remove old `shared/api/graphql/useQuery.ts` if unused
- Audit cross-entity imports against directional rules
- Final documentation pass

### Migration steps per entity

For each entity in any wave:

1. Create `ui/queries/` directory
2. Split `domain/*.query.ts` — extract queryOptions + hooks to `ui/queries/`
3. Make domain async functions accept branch/date/schema as parameters
4. If entity lacks api/ or domain/, create the missing layer
5. Verify zero React imports remain in domain/
6. Run tests
