# Apollo → TanStack Query — Migration Completion Checklist

> Companion to [`2026-05-20-apollo-tanstack-migration.md`](./2026-05-20-apollo-tanstack-migration.md). That doc covered the multi-PR migration of Apollo React hooks → TanStack Query (PRs #9305–#9310 + ple-tanstack-7-finalize). This doc covers everything still standing between "hooks migrated" and "epic closed".

## Status as of 2026-05-26

After `ple-tanstack-7-finalize` lands:

- **Apollo React hooks remaining: 0** ✅
- **`graphqlClient.*` calls outside `entities/*/api/`: 0** ✅
- **`@apollo/client` imports outside the documented allowlist (`app/app.tsx`, `shared/api/graphql/graphqlClientApollo.tsx`, `entities/*/api/`): 0** ✅
- **Old `shared/api/graphql/useQuery.ts` wrapper: deleted** ✅
- **`entities-structure.md` documents the new transport-vs-server-state split** ✅

The epic's stated scope — *"Apollo React hooks and Apollo-driven application patterns will be removed from active feature code"* — is met. Items below are hardening, consistency, and follow-up cleanup that keep the codebase healthy now that the migration is functionally done.

## Epic acceptance criteria (re-stated for closure)

- [x] TanStack Query is the only server-state hook in feature code.
- [x] Apollo Client is contained to the transport layer (allowlist above).
- [x] Existing product behavior preserved (pagination, polling, branch-aware data access, time-based query behavior).
- [x] Frontend structure docs (`entities-structure.md`, `naming-conventions.md`) reflect the new pattern.
- [x] All `entities/*/api/` files follow the `*-from-api.ts` naming convention. *(see Group A)*
- [x] Every mutation has a documented invalidation strategy — either `onSuccess`/`onSettled` in the mutation hook, or an explicit callsite-level invalidation comment. *(see Group B)*
- [x] Domain-layer return-type naming is consistent. *(see Group C)*

---

## Group A — Convention sweep: rename non-conforming api files

Pure renames + import updates. No behavior change.

| File | Target name | Notes |
|---|---|---|
| `entities/proposed-changes/api/createProposedChange.ts` | `create-proposed-change-from-api.ts` | camelCase → kebab |
| `entities/proposed-changes/api/updateProposedChangeReviewFromApi.ts` | `update-proposed-change-review-from-api.ts` | mixed case → kebab |
| `entities/nodes/api/generateRelationshipListQuery.ts` | `generate-relationship-list-query.ts` *or* move under `nodes/relationships/api/` | helper, not an API call — consider relocating |
| `entities/nodes/api/getRelationshipParent.ts` | `get-relationship-parent-from-api.ts` | likely belongs under `nodes/relationships/api/` |
| `entities/navigation/api/search.ts` | `search-from-api.ts` | |
| `entities/schema/api/dropdown.ts` | `dropdown-from-api.ts` *or* split into the existing add/remove files | check if still needed |
| `entities/schema/api/enum.ts` | `enum-from-api.ts` *or* split as above | |
| `entities/nodes/hierarchy/api/query/get-object-ancestors-query.ts` | move to `entities/nodes/hierarchy/api/get-object-ancestors-from-api.ts` | remove non-standard `query/` subfolder |
| `entities/nodes/object/api/get-display-label.ts` | `get-display-label-from-api.ts` | |

**Verification**:
```bash
find frontend/app/src/entities -type f -path '*/api/*.ts' \
  ! -name '*-from-api.ts' ! -name '*.query.ts' ! -name '*.mutation.ts'
# expected output: empty
```

**Suggested PR**: `refactor(frontend): align entities/*/api/ files with -from-api naming convention`. Size: ~9–15 files.

---

## Group B — Mutation invalidation audit

20 mutations have no `onSuccess`/`onSettled`/`invalidateQueries` in the hook itself. Some are correct (callsite handles invalidation, e.g., `resolve-conflict` is invalidated in `conflict.tsx:38-39`). Others may be genuinely missing.

### Mutations to audit

| Mutation | Likely owner of invalidation | Action |
|---|---|---|
| `authentication/logout` | callsite (`account-menu.tsx` already calls `queryClient.clear()`) | confirm + document |
| `authentication/login-with-credentials` | callsite (auth flow) | confirm |
| `authentication/login-with-ldap` | callsite (auth flow) | confirm |
| `repository/reimport-last-commit` | likely missing — should invalidate repo + tasks | check |
| `repository/import-current-commit` | likely missing — should invalidate repo + tasks | check |
| `repository/check-connectivity` | informational, may not need invalidation | confirm no-op intent |
| `resource-manager/allocate-resource` | likely missing — should invalidate pool utilization + allocated list | check |
| `artifacts/generate-artifact` | task-based, callsite probably refetches | confirm |
| `user-profile/update-account-password` | likely no invalidation needed (no cached data changes) | confirm intent |
| `user-profile/create-account-token` | should invalidate account token list | check |
| `branches/merge-branch` | callsite (`branch-merge-button.tsx` calls `refetch()`) — partial only | broaden? |
| `branches/validate-branch` | callsite (`branch-validate-button.tsx`) does NOT refetch | likely missing |
| `branches/rebase-branch` | check | |
| `diff/resolve-conflict` | callsite (`conflict.tsx:38-39`) — explicit invalidation | confirm + document |
| `diff/run-check` | check | |
| `diff/update-diff` | check | |
| `generators/run-generator` | task-based, callsite refetches | confirm |
| `schema/add-dropdown` | check | |
| `schema/add-enum` | check | |
| `schema/remove-dropdown` | check | |
| `schema/remove-enum` | check | |

### Decision needed: where should invalidation live?

Two patterns coexist today. Pick one as the standard:

**Option 1 — Invalidation in the mutation hook (recommended)**
```ts
export function useMergeBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: mergeBranch,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
}
```
Pros: invalidation is co-located with the mutation, every callsite gets it for free, easier to audit.
Cons: less flexibility per call.

**Option 2 — Invalidation at the callsite**
```ts
const mergeMutation = useMergeBranch();
const handleClick = async () => {
  await mergeMutation.mutateAsync({ branchName });
  await queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
};
```
Pros: callsite can choose what to invalidate based on context.
Cons: easy to forget, harder to audit, leads to bugs the migration already caught (commits `efae3310`, `6158690a`, `ef7d0ff2`).

Recommendation: **Option 1 as the default**, callsite-level invalidation only when the call needs context-specific behavior. Update `naming-conventions.md` accordingly.

**Verification**:
```bash
# After audit, every mutation file should either have onSuccess or a top-of-file
# comment explaining why invalidation lives at the callsite.
for f in $(find frontend/app/src/entities -name '*.mutation.ts'); do
  if ! grep -q 'onSuccess\|onSettled\|invalidation-at-callsite' "$f"; then
    echo "MISSING: $f"
  fi
done
```

**Suggested PR**: `refactor(frontend): standardize mutation invalidation across entities`. Size: ~10–20 files. Likely uncovers 2–4 real bugs.

---

## Group C — Domain-layer return-type naming

Two conventions coexist after the migration:

- `*Result` (6 existing files): `GetGroupsResult`, `SearchDocResult`, `CheckConnectivityResult`, `ImportCurrentCommitResult`, `ReimportLastCommitResult`, `ResourceAllocatedResult`
- `*Outcome` (4 new files, from `ple-tanstack-7-finalize`): `MergeBranchOutcome`, `ValidateBranchOutcome`, `CreateProposedChangeOutcome`, `AddDropdownOutcome`

Decide one. `*Result` is the established majority and is more conventional. Recommendation: rename `*Outcome` → `*Result`.

**Verification**:
```bash
rg 'export (interface|type) \w+(Outcome|Result)\b' frontend/app/src/entities -g '*.ts'
# expect all matches to use the same suffix
```

**Suggested PR**: tiny — `refactor(frontend): align domain return types on *Result naming`. Or fold into Group A.

---

## Group D — Documentation polish

Update these docs once Groups A/B/C are merged:

- `dev/guidelines/frontend/naming-conventions.md`
  - Add the mutation-invalidation convention chosen in Group B.
  - Reiterate the `*-from-api.ts` requirement for `entities/*/api/` (it's there, but make it stronger now that Group A enforces it).
- `dev/knowledge/frontend/entities-structure.md`
  - Add a one-liner stating Apollo runs with `fetchPolicy: "no-cache"` and the `InMemoryCache` is unused — so future contributors don't accidentally re-enable Apollo caching and create a two-cache problem.
- `docs/superpowers/plans/2026-05-20-apollo-tanstack-migration.md`
  - Add a top-level "✅ COMPLETED" banner once Groups A/B/C are done.

---

## Stretch — Group 8: Full Apollo removal (NOT part of this epic)

The epic explicitly says *"Apollo Client will remain in place for now as a low-level transport utility for API calls, authentication, and retry handling"*, so this is out of scope. Captured here so it isn't forgotten:

### Motivation

The epic's "we globally disable Apollo's normalized cache (`no-cache` on all queries), shipping ~40 KB gzipped of library code that does nothing" only becomes a real bundle win if Apollo transport is also removed.

### Inventory of what Apollo currently does (must be reproduced)

- **Transport** — `graphqlClient.query/.mutate` called from ~80 `entities/*/api/` files.
- **`gql` tag** — used in ~30 api files to parse query strings into DocumentNode.
- **`setContext` link** — injects `Authorization: Bearer <token>` from `localStorage`, plus branch/date into the URL.
- **`onError` link** — handles GraphQL errors:
  - `code === 401` → refresh access token via `queryClient.fetchQuery(refreshAccessTokenQueryOptions())`, retry operation
  - `code === 403` → silent (no toast)
  - default → call `processErrorMessage(message)` from operation context, fallback to global toast
- **`createUploadLink`** (apollo-upload-client) — multipart file uploads (used by repo/file edit paths).
- **`InMemoryCache`** — allocated but unused (no-cache fetchPolicy).
- **No GraphQL subscriptions** — `graphqlClient.subscribe` is not called anywhere.

### Suggested phasing

1. **Build the replacement transport** (`shared/api/graphql/graphqlClient.ts`)
   - Plain `fetch`-based client with the same context API (`branch`, `date`, `processErrorMessage`).
   - Auth header injection + 401 refresh-and-retry (port from `setContext` + `errorLink`).
   - Multipart upload code path using `extract-files` + FormData (port from `createUploadLink`).
   - 403 silent / default toast behavior (port from `errorLink`).
   - Returns `{ data, errors }` to match Apollo's call signature so api files don't need to change shape.
2. **Migrate api files entity-by-entity** (mirrors the original migration cadence — small focused PRs).
3. **Replace `gql` imports** with `graphql-tag` package (or raw template strings).
4. **Delete `graphqlClientApollo.tsx`, `ApolloProvider` in `app.tsx`, all `@apollo/client` + `apollo-upload-client` deps.**
5. **Update `entities-structure.md`** to ban Apollo entirely.

Bundle impact: ~40 KB gzipped removed. Maintenance: simpler mental model (one cache, one transport).

---

## Definition of done for this epic

- [x] Group A merged (api file naming).
- [x] Group B merged (mutation invalidation standardized + audit completed).
- [x] Group C merged (domain return-type naming aligned).
- [x] Group D merged (docs updated).
- [x] `2026-05-20-apollo-tanstack-migration.md` banner updated to "✅ COMPLETED".
- [ ] Epic ticket closed.

Group 8 (full Apollo removal) is tracked separately if/when the team decides to pursue the bundle-size win.

## Tracking

Each group should be its own PR with a link back to this doc. When all four merge, close the epic.
