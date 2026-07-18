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

## GraphQL fetching: go through the entity layer

The `ui/` layer **never** builds `gql` strings inline or calls `graphqlClient.query` directly. Either:

1. Use a hook from another entity's `ui/queries/` (e.g. `useGetObject` from `entities/nodes/object`).
2. Add a new fetcher: `api/get-{noun}-from-api.ts` → `domain/get-{noun}.ts` → `ui/queries/get-{noun}.query.ts`.

Inline `gql` in `ui/` bypasses caching, branch context, schema typing, and the layered architecture. It is a pattern bug, not a shortcut.

### Single-object reads

For "I have a UUID, give me the node", always use `useGetObject({ objectId, objectSchema: { kind: "CoreNode" } })` from `entities/nodes/object/ui/queries/get-object.query.ts`. Do not write a one-off `resolveUuid` function.

## Backend is authoritative

If the server defaults, filters, sorts, or hides something, the client must not maintain a parallel constant. Examples:

- Default namespace exclusions (Core, Internal, Builtin, Lineage, Profile, Template) are applied server-side. Do not duplicate them in a client `HIDDEN_NAMESPACES` constant.
- Schema kinds and their hidden flags come from `useGetSchema`.
- Pagination defaults, sort order, and ACL checks live on the server.

If the client genuinely needs to display a server-side default, surface it via the API response — do not mirror the constant.

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

## GraphQL transport vs server-state hooks

Apollo Client is kept as the GraphQL transport (auth links, error handling, retry) only. All server-state hooks are TanStack Query. Do not use `useQuery` / `useMutation` / `useLazyQuery` from `@apollo/client` — they were removed in 2026-05.

- `@apollo/client` imports are allowed **only** in `src/app/app.tsx` (for `ApolloProvider`) and `src/shared/api/graphql/graphqlClientApollo.tsx` (client construction), plus `gql` template-tag imports in `entities/*/api/` files.
- React hooks (`useQuery`, `useMutation`, etc.) from `@apollo/client` are forbidden throughout the codebase.
- Use `useQuery` / `useMutation` from `@tanstack/react-query` (typically via the pattern in `ui/queries/`) for all data fetching.

### One cache, not two

Apollo is configured with `defaultOptions: { query: { fetchPolicy: "no-cache" }, mutate: { fetchPolicy: "no-cache" } }`. Its `InMemoryCache` instance exists for API-surface reasons only — nothing ever reads from it. **TanStack Query is the only server-state cache.**

Do not enable Apollo's normalized cache, do not pass `fetchPolicy: "cache-first"` (or similar) at any callsite, and do not start consuming `apolloClient.cache.readQuery` / `writeQuery`. Doing so creates a two-cache problem: TanStack's invalidation will not touch Apollo's cache, leading to stale reads that look like data-loading bugs.

### Mutation invalidation

Mutations own their cache invalidation. Place `onSuccess`/`onSettled` inside the `useMutation` hook in `ui/queries/*.mutation.ts`. See `dev/guidelines/frontend/naming-conventions.md#mutation-invalidation` for the convention and the audit script.
