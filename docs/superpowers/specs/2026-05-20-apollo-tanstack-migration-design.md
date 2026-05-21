# Complete Apollo → TanStack Query Migration

**Status:** Design
**Date:** 2026-05-20
**Owner:** paul@opsmill.com

## Context

The frontend has been progressively migrating from Apollo's React hooks to TanStack Query. The migration started organically — new features used TanStack Query while older code stayed on Apollo — and was never formally tracked. Today 98 files use TanStack Query; a small remainder still call Apollo's `useQuery`/`useMutation`. This spec finishes the migration.

The migration is motivated by:

- **Consistency.** Two server-state patterns running side-by-side make the codebase harder to read and onboard into.
- **Caching.** Apollo's normalized cache is globally disabled (`no-cache` on every query). The kept code provides no caching value, while the new TanStack code uses its caching effectively.
- **Bundle weight.** `@apollo/client/react` ships ~40 KB gzipped of React-hook code that does nothing once `no-cache` is set everywhere.
- **AI-assisted development.** Mixed patterns increase the chance of generated code following the wrong example.

## Goals

1. Remove all Apollo React hook usage (`useQuery`, `useMutation`, `useLazyQuery`, `useReactiveVar`, `useSubscription`) from `src/`.
2. Delete the shared wrapper `src/shared/api/graphql/useQuery.ts`.
3. Preserve current product behavior — pagination, polling, branch-aware data, time-machine queries.
4. Update `dev/knowledge/frontend/` so future contributors and AI agents see one pattern.

## Non-goals

- **Removing `ApolloClient`.** It stays as the GraphQL transport (auth links, error links, retry behavior). The proposal explicitly keeps it.
- **Removing `gql` template tag imports.** They are tag-literal calls used to build query strings for the kept Apollo client; replacing them adds churn with no runtime benefit. Track as a follow-up if codegen-based queries become a preference.
- **Schema or backend changes.**
- **Rewriting unrelated code in touched files.** Focused changes only.

## Current State (audit)

### Apollo hook callers — must migrate

Files importing `useQuery` / `useMutation` / `useLazyQuery` from `@apollo/client` (directly or via the shared wrapper):

**Shared wrapper:**

- `src/shared/api/graphql/useQuery.ts` — re-exports Apollo's hooks with branch + date + pagination injection. Deleted at end of migration.

**Feature code (direct Apollo or via wrapper):**

1. `src/entities/branches/ui/branch-merge-button.tsx`
2. `src/entities/branches/ui/branch-validate-button.tsx`
3. `src/entities/branches/ui/branch-rebase-button.tsx`
4. `src/entities/diff/ui/node-diff/comments.tsx`
5. `src/entities/diff/ui/node-diff/thread.tsx`
6. `src/entities/diff/ui/artifact-diff/artifact-content-diff.tsx`
7. `src/entities/diff/ui/file-diff/file-content-diff.tsx`
8. `src/shared/components/ui/id.tsx`
9. `src/shared/components/form/generic-selector.tsx`
10. `src/shared/components/inputs/relationship-one.tsx`
11. `src/pages/proposed-changes/new.tsx`
12. `src/entities/proposed-changes/ui/proposed-change-edit-trigger.tsx`
13. `src/entities/proposed-changes/ui/conversations/thread.tsx`
14. `src/entities/nodes/object-item-edit/object-item-edit-paginated.tsx`
15. `src/entities/nodes/object/ui/queries/delete-objects.mutation.ts`

### Apollo enum usage in tests

- `src/entities/tasks/ui/task-status.test.tsx` — uses `NetworkStatus`
- `src/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch.test.ts` — uses `NetworkStatus`

These tests assert on Apollo network-status enums (`NetworkStatus.loading`, `NetworkStatus.ready`, etc.). They must move to TanStack equivalents (`status: 'pending' | 'success' | 'error'`, `fetchStatus: 'fetching' | 'idle' | 'paused'`).

### Stays as-is

- `src/app/app.tsx` — `ApolloProvider` wrapping the app.
- `src/shared/api/graphql/graphqlClientApollo.tsx` — client construction, links, error handling.
- All `gql` tag imports across `entities/*/api/*-from-api.ts` files. These are tag literals consumed by the kept Apollo client.

## Target Pattern (already established)

`entities/resource-manager` is the canonical example. Each migrated feature lands as four files:

```text
entities/<feature>/
  api/get-<x>-from-api.ts            # graphqlClient.query/mutate call, raw GraphQL types
  domain/get-<x>.ts                  # typed function, throws on error, returns plain data
  ui/queries/<feature>.query-keys.ts # query key factory
  ui/queries/get-<x>.query.ts        # queryOptions + useGetX() hook; injects branch + datetime
```

Branch and time-machine context are pulled inside the `useGetX` hook via:

- `useCurrentBranch()` from `entities/branches/ui/branches-provider`
- `useAtomValue(datetimeAtom)` from `shared/stores/time.atom`

Pagination (previously auto-injected by the shared wrapper via `usePagination()`) is passed explicitly by callers. Each caller is audited during migration to confirm whether it actually needs `offset`/`limit`.

## Migration Sequencing

Seven groups, lowest blast radius first. Each group is its own PR so it can be reviewed and reverted independently.

### Group 1 — Branch action buttons (3 files)

- `branch-merge-button.tsx`
- `branch-validate-button.tsx`
- `branch-rebase-button.tsx`

Isolated trigger components. **Watch:** `branch-validate-button.tsx` likely uses Apollo `pollInterval` — map to TanStack `refetchInterval`. Verify behavior around tab focus / window visibility (TanStack defaults differ from Apollo).

### Group 2 — Diff readers (4 files)

- `node-diff/comments.tsx`
- `node-diff/thread.tsx`
- `artifact-diff/artifact-content-diff.tsx`
- `file-diff/file-content-diff.tsx`

Read-only paths. Migrate straightforwardly into entity `ui/queries/` files.

### Group 3 — Shared form inputs (3 files)

- `shared/components/ui/id.tsx`
- `shared/components/form/generic-selector.tsx`
- `shared/components/inputs/relationship-one.tsx`

Touched by many pages. Deliberately scheduled **after** Groups 1–2 so the pattern is proven before changing components with broad usage. Regression risk concentrated in object create/edit forms.

### Group 4 — Proposed changes (3 files)

- `pages/proposed-changes/new.tsx`
- `entities/proposed-changes/ui/proposed-change-edit-trigger.tsx`
- `entities/proposed-changes/ui/conversations/thread.tsx`

Co-located feature. Migrate together so query keys and invalidation are consistent.

### Group 5 — Object item edit (2 files)

- `entities/nodes/object-item-edit/object-item-edit-paginated.tsx`
- `entities/nodes/object/ui/queries/delete-objects.mutation.ts`

Last feature on Apollo hooks. Pagination explicit (no more wrapper auto-injection).

### Group 6 — Tests (2 files)

- `task-status.test.tsx`
- `is-task-running-on-branch.test.ts`

Replace `NetworkStatus` assertions with TanStack `status`/`fetchStatus` equivalents.

### Group 7 — Wrapper removal + cleanup

- Delete `src/shared/api/graphql/useQuery.ts`.
- Grep `src/` for any remaining `from '@apollo/client'` imports that aren't `gql`, `graphqlClient`, `ApolloProvider`, or `ApolloClient` construction. Should be zero.
- Run `pnpm build` and capture bundle size; confirm reduction ~40 KB gzip vs. baseline captured before Group 1.
- Update `dev/knowledge/frontend/entities-structure.md` and any guideline referring to Apollo hooks. Add a note that Apollo remains as transport only.

## Polling & Pagination — Behavior Preservation

Two subtleties that must be handled per-caller during migration:

**Polling.** Apollo's `pollInterval` polls at a fixed cadence and keeps polling while the tab is hidden. TanStack's `refetchInterval` pauses when the tab is hidden by default. For each migrated polling call, confirm whether background polling is desirable; if it is, set `refetchIntervalInBackground: true`.

**Pagination.** The shared wrapper injects `{ offset, limit }` from `usePagination()` into every query's `variables`. Migration breaks this implicit contract. For each caller using the wrapper, check whether the query actually uses `$offset` / `$limit`. If yes, the new `useGetX` hook accepts pagination params from the caller (typically via `usePagination()` at the call site).

## Done Criteria

- `rg "from ['\"]@apollo/client['\"]" frontend/app/src` returns only: `ApolloProvider` (app.tsx), `ApolloClient`/`InMemoryCache`/links (graphqlClientApollo.tsx), and `gql` tag imports. Zero hook imports.
- `src/shared/api/graphql/useQuery.ts` is deleted.
- `pnpm build` succeeds.
- `pnpm test` and `pnpm test:e2e` pass.
- Bundle size report shows ~40 KB gzip reduction vs. baseline captured at start of Group 1.
- `dev/knowledge/frontend/` updated: Apollo described as transport-only; TanStack Query is the documented server-state pattern.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Polling semantics differ (tab-hidden behavior). | Per-caller audit in Group 1; set `refetchIntervalInBackground` where existing behavior depended on background polling. |
| Implicit pagination injection removed. | Per-caller audit; make pagination params explicit in the new hook signature. |
| Shared inputs (Group 3) touch many pages. | Done after Groups 1–2 so the pattern is proven. Manual smoke-test object create/edit flows in E2E and dev server. |
| Behavior drift in proposed-changes (Group 4) — multiple files interact. | Migrate as one PR; keep query keys aligned so invalidation flows still work. |
| Bundle reduction smaller than expected. | Acceptable — primary value is consistency. Note in PR description and continue. |
| `@apollo/client/react` still tree-shaken in? | Final cleanup step: verify with `vite build --report` (or equivalent) that the `react` subpath is no longer in the bundle. |

## Out of Scope (Follow-ups)

- Removing `gql` tag imports and adopting a single query-source pattern (codegen-generated documents, or `graphql-tag` direct). Track as a separate epic if desired.
- Removing the kept Apollo transport in favor of a thinner GraphQL fetch helper. Not part of this work.
