# Frontend Entities Structure

Location: `frontend/app/src/entities/`

## Three-Layer Architecture

Each entity is organized into three layers with strict import rules. Dependencies flow in one direction: ui/ -> domain/ -> api/.

`api/` and `ui/` structure is unchanged from earlier revisions. What changed (2026-07): `domain/` is split into `model/` / `rules/` / `use-cases/` when it grows past 4 files, and generated↔domain **mappers now live in `api/`** (not `domain/`).

```text
entities/{name}/
├── api/                              # Transport + anti-corruption. Flat (no subfolders).
│   ├── get-{noun}-from-api.ts        # Raw GraphQL/REST call (owns generated wire types)
│   ├── create-{noun}-from-api.ts
│   └── {noun}.mappers.ts             # generated wire shape → DOMAIN type. Imports domain/model (type-only).
├── domain/                           # Business core — framework-free TypeScript
│   ├── model/                        # Domain vocabulary: types, IDs, filters, sorts, inputs, results
│   │   └── {noun}.ts                 # MAY import generated enums/scalars (e.g. BranchStatus) as value types
│   ├── rules/                        # Pure functions, no I/O (e.g. filter extraction)
│   │   └── {noun}-filters.ts
│   └── use-cases/                    # Orchestration; calls own api/ (incl. its mappers)
│       ├── get-{noun}.ts
│       └── create-{noun}.ts
└── ui/                               # React — framework integration (nested subfolders OK)
    ├── queries/
    │   ├── {noun}.query-keys.ts      # Query key factory
    │   ├── get-{noun}.query.ts       # queryOptions factory + useQuery hook
    │   └── create-{noun}.mutation.ts # useMutation hook + cache invalidation
    ├── hooks/
    │   └── use-{noun}-{thing}.ts     # Entity-specific React hooks
    └── {noun}-table.tsx              # React components
```

### When to split `domain/`

Split into `model/`+`rules/`+`use-cases/` **only when `domain/` has more than 4 files**; below that, keep it flat. **Never create a subfolder to hold fewer than 2 files.** Classify each file: type declarations → `model/`; pure no-I/O functions → `rules/`; orchestration that calls `api/` → `use-cases/`. Small entities (e.g. `config`, `role-manager`) stay flat.

### Generated types: DTOs vs enums

- **Wire-shape response DTOs** (e.g. `InfrahubBranch`, `InfrahubNodeMetadata`) and the **mappers** that consume them live in `api/`. They never appear in `domain/`.
- **Generated enums / scalar value-types** (e.g. `BranchStatus`) **may** be imported into `domain/model` as value types — re-declaring them as domain-local types is unnecessary churn (YAGNI). The goal is to keep the *wire format* out of `domain/`, not every generated symbol.

### Enforcement

Boundaries are enforced by **code review** against this document. There is no automated lint guard. (A dependency-cruiser-based guard was considered and deferred; adding it is a separate new-dependency decision.)

## Layer Rules

| Layer | Allowed imports | Prohibited |
|-------|----------------|------------|
| **api/** | `shared/api/`, own `domain/model` (type-only, for mapper return types) | `domain/rules`, `domain/use-cases`, `ui/`, other entities |
| **domain/model** | `shared/` types, generated enums/scalars, other entities' `domain/model` | `api/`, `domain/rules`, `domain/use-cases`, `ui/` (pure leaf) |
| **domain/rules** | own `domain/model`, `shared/` | `api/`, `ui/`, React, TanStack, Jotai, generated wire DTOs |
| **domain/use-cases** | own `api/` (incl. mappers), own `domain/model` + `rules`, `shared/` | `ui/`, React, TanStack, Jotai, generated wire DTOs |
| **ui/** | `domain/` (same entity), `shared/`, other entities' `domain/` and `ui/` | Another entity's `api/` |

Key constraints: no circular dependencies (the graph must be a DAG); `domain/model` is a pure leaf so `api → domain/model` + `domain → api` stays acyclic. Generated **wire DTOs** never enter `domain/`; generated **enums** may (see above).

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
// domain/use-cases/get-branches.ts — pure, no framework imports
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

Mappers (generated wire shape ↔ domain type) live in **`api/`**, e.g. `api/{noun}.mappers.ts`. They import the generated types and return `domain/model` types (the only place `api/` imports `domain/`, and type-only). A `domain/use-cases/` function calls its own `api/` fetcher and mapper; it never imports a generated wire type itself. For a trivial mapping, inline it in the `api/` fetcher rather than a separate mappers file.

## GraphQL fetching: go through the entity layer

The `ui/` layer **never** builds `gql` strings inline or calls `graphqlClient.query` directly. Either:

1. Use a hook from another entity's `ui/queries/` (e.g. `useGetObject` from `entities/nodes/object`).
2. Add a new fetcher: `api/get-{noun}-from-api.ts` → `domain/use-cases/get-{noun}.ts` (flat `domain/get-{noun}.ts` if the entity is unsplit) → `ui/queries/get-{noun}.query.ts`.

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

`branches` is the canonical migrated entity (11 domain files → split).

```text
entities/branches/
├── api/
│   ├── get-branches-from-api.ts      # raw GraphQL call
│   ├── create-branch-from-api.ts
│   └── branch.mappers.ts             # mapToBranchListItem/Detail, InfrahubBranchResponse DTO
├── domain/
│   ├── model/
│   │   └── branch.ts                 # BranchListItem, BranchDetail (imports generated BranchStatus)
│   ├── rules/
│   │   └── branch-filters.ts         # pure filter-extraction helpers
│   └── use-cases/
│       ├── get-branches.ts           # calls api fetcher + api mapper; extracts filters via rules
│       ├── create-branch.ts
│       └── … (delete/merge/rebase/validate/…)
└── ui/
    ├── queries/
    │   ├── branch.query-keys.ts
    │   ├── get-branches.query.ts
    │   └── create-branch.mutation.ts
    ├── branches-table.tsx
    └── branches-provider.tsx
```

Note: `model/` and `rules/` hold a single file each here — acceptable for a fully-split reference entity so all three domain roles are visible. A use-case (`domain/use-cases/get-branches.ts`) imports its mapper from `api/branch.mappers.ts` (allowed: `use-cases → own api/`).

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
