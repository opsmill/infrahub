# Frontend Entities Structure

Location: `frontend/app/src/entities/`

## Three-Layer Architecture

Each entity is organized into three layers with strict import rules. Dependencies flow in one direction: ui/ -> domain/ -> api/.

```text
entities/{name}/
├── api/                              # Transport — raw network calls
│   ├── get-{noun}-from-api.ts
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

## Layer Rules

| Layer | Allowed imports | Prohibited |
|-------|----------------|------------|
| **api/** | `shared/api/` only | React, domain/, other entities |
| **domain/** | `api/` (same entity), `shared/utils/`, other entities' `domain/` | React, TanStack, Jotai |
| **ui/** | `domain/` (same entity), `shared/`, other entities' `domain/` and `ui/` | Another entity's `api/` |

Key constraint: no circular dependencies between entities. The dependency graph must be a DAG.

## Data Flow

```text
Page (thin route wrapper)
  └── ui/ component (renders, handles user interaction)
        └── ui/queries/ hook (reads branch/date from context, calls queryOptions)
              └── domain/ async function (calls api, transforms response)
                    └── api/ function (raw network call)
```

Global state (branch, date, schema) is injected at the ui/ layer and passed as parameters to domain/ functions. Domain functions never read global state directly.

## queryOptions Live in ui/queries/

queryOptions factories and useQuery/useMutation hooks live in `ui/queries/`, not in domain/. Domain's public API is async functions and types only.

Rationale: `queryOptions` configures TanStack Query, a framework concern. Caching strategy, query keys, and reactive subscriptions belong in the UI layer. A TUI or CLI would call domain async functions directly without TanStack.

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

## Cross-Entity Imports

Import from another entity's `domain/` (types, async functions) or `ui/` (hooks, components). Never import from another entity's `api/`.

```ts
// Allowed: importing another entity's domain types
import type { SchemaNode } from "@/entities/schema/domain/schema.types";

// Allowed: importing another entity's UI hook
import { useGetSchema } from "@/entities/schema/ui/queries/get-schema.query";

// Prohibited: importing another entity's api/
import { getSchemaFromApi } from "@/entities/schema/api/get-schema-from-api"; // NEVER
```

## Mappers

Mappers are optional. Use them only when transformation is non-trivial (more than 5-6 lines of field access). For simple entities, inline the transformation in the domain async function.

## Reference Example: branches

```text
entities/branches/
├── api/
│   ├── get-branches-from-api.ts
│   └── create-branch-from-api.ts
├── domain/
│   ├── branch.types.ts
│   ├── get-branches.ts
│   └── create-branch.ts
└── ui/
    ├── queries/
    │   ├── branch.query-keys.ts
    │   ├── get-branches.query.ts
    │   └── create-branch.mutation.ts
    ├── branches-table.tsx
    └── branches-provider.tsx
```

## File Naming

See `dev/guidelines/frontend/naming-conventions.md` for the full naming conventions table.
