# Frontend Layered Architecture Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all 23 frontend entities to the layered architecture defined in `docs/plans/2026-02-28-frontend-layered-architecture-design.md`.

**Architecture:** Three-layer separation (api/ → domain/ → ui/) where domain/ has zero framework imports. queryOptions, query keys, and hooks move from domain/ to ui/queries/. Domain functions accept branch/date/schema as parameters instead of reading from React context.

**Tech Stack:** TypeScript 5.9, React 19.2, TanStack Query, Jotai, Apollo GraphQL (transport only), gql.tada

---

## Standard Migration Recipe

Every entity follows this recipe unless noted otherwise. Wave-specific tasks list deviations.

### Step A: Create ui/queries/ directory

```bash
mkdir -p src/entities/{name}/ui/queries
```

### Step B: Move query keys file

Move `domain/{name}.query-keys.ts` → `ui/queries/{name}.query-keys.ts`

Update all imports across the codebase:
```bash
cd frontend/app && grep -r "domain/{name}.query-keys" src/ --include="*.ts" --include="*.tsx" -l
```

### Step C: Split each domain/*.query.ts file

For each `domain/get-{noun}.query.ts`:

1. Move the entire file to `ui/queries/get-{noun}.query.ts`
2. If the `queryOptions` factory already takes branch/date as parameters (not from hooks), no domain changes needed
3. If the hook reads `useCurrentBranch`/`useAtomValue(datetimeAtom)` — this stays in ui/queries/ (correct location now)
4. Update all imports across the codebase

### Step D: Split each domain/*.mutation.ts file

Same as Step C but for `domain/create-{noun}.mutation.ts` → `ui/queries/create-{noun}.mutation.ts`

### Step E: Move React hooks out of domain/

If any `domain/*.ts` file (non-query, non-mutation) imports React hooks, extract the hook part to `ui/hooks/` and keep the pure function in domain/.

### Step F: Verify and test

```bash
# Verify no React/TanStack/Jotai imports in domain/
grep -r "from \"react\"" src/entities/{name}/domain/ --include="*.ts"
grep -r "from \"@tanstack" src/entities/{name}/domain/ --include="*.ts"
grep -r "from \"jotai\"" src/entities/{name}/domain/ --include="*.ts"
grep -r "useCurrentBranch" src/entities/{name}/domain/ --include="*.ts"
grep -r "useAtomValue" src/entities/{name}/domain/ --include="*.ts"

# Run tests
npm run test
npm run build
```

### Step G: Commit

```bash
git add src/entities/{name}/
git commit -m "refactor({name}): migrate to layered architecture"
```

---

## Task 1: Update documentation

**Files:**
- Modify: `dev/guidelines/frontend/naming-conventions.md`
- Modify: `dev/knowledge/frontend/entities-structure.md`
- Modify: `frontend/app/AGENTS.md`

**Step 1: Update naming conventions**

Replace the current entities section in `dev/guidelines/frontend/naming-conventions.md` with:

```markdown
| Directory | Pattern | Example |
|-----------|---------|---------|
| `entities/{name}/api/` | `verb-noun-from-api.ts` | `get-branches-from-api.ts` |
| `entities/{name}/domain/` | `verb-noun.ts` | `get-branches.ts` |
| `entities/{name}/domain/` | `{noun}.types.ts` | `branch.types.ts` |
| `entities/{name}/domain/` | `{noun}.mappers.ts` | `branch.mappers.ts` (optional) |
| `entities/{name}/ui/queries/` | `verb-noun.query.ts` | `get-branches.query.ts` |
| `entities/{name}/ui/queries/` | `verb-noun.mutation.ts` | `create-branch.mutation.ts` |
| `entities/{name}/ui/queries/` | `{noun}.query-keys.ts` | `branch.query-keys.ts` |
| `entities/{name}/ui/` | `kebab-case.tsx` | `branches-table.tsx` |
```

**Step 2: Update entities-structure.md**

Rewrite to reflect the new architecture: domain/ has zero framework imports, queryOptions live in ui/queries/, domain functions accept context as parameters.

**Step 3: Commit**

```bash
git add dev/guidelines/ dev/knowledge/ frontend/app/AGENTS.md
git commit -m "docs: update frontend architecture guidelines for layered migration"
```

---

## Task 2: Wave 1 — branches (reference implementation)

**Files:**
- Create: `src/entities/branches/ui/queries/branch.query-keys.ts`
- Create: `src/entities/branches/ui/queries/get-branches.query.ts`
- Create: `src/entities/branches/ui/queries/get-branch-details.query.ts`
- Create: `src/entities/branches/ui/queries/get-branches-count.query.ts`
- Create: `src/entities/branches/ui/queries/create-branch.mutation.ts`
- Create: `src/entities/branches/ui/queries/delete-branch.mutation.ts`
- Create: `src/entities/branches/ui/queries/delete-branches.mutation.ts`
- Create: `src/entities/branches/ui/queries/rebase-branch.mutation.ts`
- Move: `src/entities/branches/ui/hooks/use-branch-exists.ts` (from domain/)
- Delete: `src/entities/branches/domain/branch.query-keys.ts`
- Delete: `src/entities/branches/domain/get-branches.query.ts`
- Delete: `src/entities/branches/domain/get-branch-details.query.ts`
- Delete: `src/entities/branches/domain/get-branches-count.query.ts`
- Delete: `src/entities/branches/domain/create-branch.mutation.ts`
- Delete: `src/entities/branches/domain/delete-branch.mutation.ts`
- Delete: `src/entities/branches/domain/delete-branches.mutation.ts`

**Step 1: Create ui/queries/ and ui/hooks/ directories**

```bash
mkdir -p src/entities/branches/ui/queries
mkdir -p src/entities/branches/ui/hooks
```

**Step 2: Move branch.query-keys.ts**

Move `domain/branch.query-keys.ts` → `ui/queries/branch.query-keys.ts`. No content changes needed — this file has no React imports.

**Step 3: Move get-branches.query.ts**

Move `domain/get-branches.query.ts` → `ui/queries/get-branches.query.ts`. Update internal imports to point to new query-keys location.

**Step 4: Move get-branch-details.query.ts**

Move `domain/get-branch-details.query.ts` → `ui/queries/get-branch-details.query.ts`.

**Step 5: Move get-branches-count.query.ts**

Move `domain/get-branches-count.query.ts` → `ui/queries/get-branches-count.query.ts`.

**Step 6: Move mutation files**

Move each mutation file from `domain/` to `ui/queries/`:
- `create-branch.mutation.ts`
- `delete-branch.mutation.ts`
- `delete-branches.mutation.ts`

**Step 7: Split rebase-branch.ts**

`domain/rebase-branch.ts` currently exports both the plain function AND the `useRebaseBranch` hook. Split it:
- Keep the pure `rebaseBranch` async function in `domain/rebase-branch.ts`
- Extract `useRebaseBranch` hook to `ui/queries/rebase-branch.mutation.ts`

**Step 8: Move use-branch-exists.ts**

`domain/use-branch-exists.ts` uses `useAtomValue` — it's a React hook. Move to `ui/hooks/use-branch-exists.ts`.

**Step 9: Update all imports across the codebase**

Find and update every import that references the moved files. Key search patterns:

```bash
grep -r "branches/domain/branch.query-keys" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/get-branches.query" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/get-branch-details.query" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/get-branches-count.query" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/create-branch.mutation" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/delete-branch.mutation" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/delete-branches.mutation" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/rebase-branch" src/ --include="*.ts" --include="*.tsx" -l
grep -r "branches/domain/use-branch-exists" src/ --include="*.ts" --include="*.tsx" -l
```

Update import paths from `@/entities/branches/domain/...` to `@/entities/branches/ui/queries/...` or `@/entities/branches/ui/hooks/...`.

**Step 10: Verify domain/ is clean**

```bash
grep -r "from \"react\"" src/entities/branches/domain/ --include="*.ts"
grep -r "from \"@tanstack" src/entities/branches/domain/ --include="*.ts"
grep -r "from \"jotai\"" src/entities/branches/domain/ --include="*.ts"
```

Expected: zero matches.

**Step 11: Run tests and build**

```bash
npm run test
npm run build
```

**Step 12: Commit**

```bash
git add -A src/entities/branches/ && git add -u
git commit -m "refactor(branches): migrate to layered architecture - reference implementation"
```

---

## Task 3: Wave 2 — artifacts

**Files to move from domain/ to ui/queries/:**
- `domain/artifacts.query-keys.ts` → `ui/queries/artifacts.query-keys.ts`
- `domain/get-artifact-file.query.ts` → `ui/queries/get-artifact-file.query.ts`
- `domain/generate-artifact.mutation.ts` → `ui/queries/generate-artifact.mutation.ts`

Follow the standard migration recipe (Steps A–G).

Note: `generate-artifact.mutation.ts` imports `useCurrentBranch` — this stays since it's now in ui/.

**Types file**: `types.ts` sits at entity root. Move to `domain/artifacts.types.ts` for consistency.

---

## Task 4: Wave 2 — authentication

**Files to move from domain/ to ui/queries/:**
- `domain/login-with-credentials.mutation.ts` → `ui/queries/login-with-credentials.mutation.ts`
- `domain/logout.mutation.ts` → `ui/queries/logout.mutation.ts`
- `domain/refresh-access-token.query.ts` → `ui/queries/refresh-access-token.query.ts`

Follow the standard migration recipe.

Note: These files are already clean — `refresh-access-token.query.ts` has no hooks, mutation files use only `useMutation`/`mutationOptions`.

**Types file**: `types.ts` at entity root → `domain/authentication.types.ts`.

---

## Task 5: Wave 2 — config

**Files to move from domain/ to ui/queries/:**
- `domain/get-config.query.ts` → `ui/queries/get-config.query.ts`
- `domain/get-app-info.query.ts` → `ui/queries/get-app-info.query.ts`

Follow the standard migration recipe.

Note: Inline query keys (`["config"]`, `["app-info"]`) — optionally extract to a `ui/queries/config.query-keys.ts` or leave inline. Low priority.

**Types file**: `types.ts` at entity root → `domain/config.types.ts`.

---

## Task 6: Wave 2 — object-file

**Files to move from domain/ to ui/queries/:**
- `domain/object-file.query-keys.ts` → `ui/queries/object-file.query-keys.ts`
- `domain/get-object-file.query.ts` → `ui/queries/get-object-file.query.ts`

Follow the standard migration recipe.

Note: `object-file.query-keys.ts` imports from `nodes/object/domain/object.query-keys`. This cross-entity dependency will change path when nodes/object is migrated in Wave 7. Add a TODO comment for now.

---

## Task 7: Wave 2 — user-profile

**Files to move from domain/ to ui/queries/:**
- `domain/get-infrahub-account-token.query.ts` → `ui/queries/get-infrahub-account-token.query.ts`
- `domain/create-account-token.mutation.ts` → `ui/queries/create-account-token.mutation.ts`

Follow the standard migration recipe.

Note: Legacy api files (`getProfileDetails.ts`, `updateAccountPassword.ts`) use Handlebars and bare DocumentNode exports. These are out of scope for layer migration — flag for future cleanup.

---

## Task 8: Wave 2 — generators

**Files to move from domain/ to ui/queries/:**
- `domain/run-generator.mutation.ts` → `ui/queries/run-generator.mutation.ts`

Follow the standard migration recipe.

Single file move. `run-generator.mutation.ts` imports `useCurrentBranch` — stays in ui/.

---

## Task 9: Wave 3 — events

**Files to move from domain/ to ui/queries/:**
- `domain/get-events.query.ts` → `ui/queries/get-events.query.ts`
- `domain/get-event-details.query.ts` → `ui/queries/get-event-details.query.ts`

Follow the standard migration recipe.

Note: No `useCurrentBranch` or `useAtomValue` in these files — events are branch-agnostic. Inline query keys `["events", ...]` — optionally extract.

---

## Task 10: Wave 3 — navigation

**Files to move from domain/ to ui/queries/:**
- `domain/search-anywhere.query-keys.ts` → `ui/queries/search-anywhere.query-keys.ts`
- `domain/get-menu.query.ts` → `ui/queries/get-menu.query.ts`
- `domain/search-anywhere.query.ts` → `ui/queries/search-anywhere.query.ts`
- `domain/search-docs.query.ts` → `ui/queries/search-docs.query.ts`

Follow the standard migration recipe.

Note: `get-menu.query.ts` and `search-anywhere.query.ts` both use `useCurrentBranch` + `useAtomValue(datetimeAtom)` — stays in ui/. `search-docs.query.ts` has no branch context — clean already.

---

## Task 11: Wave 3 — schema

**Files to move from domain/ to ui/queries/:**
- `domain/get-schema-hash.query.ts` → `ui/queries/get-schema-hash.query.ts`
- `domain/load-schema.query.ts` → `ui/queries/load-schema.query.ts`

Follow the standard migration recipe.

Both files use `useCurrentBranch` + `useAtomValue` — stays in ui/.

Note: `domain/get-schema.ts` uses `store.get(...)` (Jotai imperative API). This is NOT a React hook — it's a synchronous read of a Jotai atom outside React. This is acceptable in domain/ since it doesn't depend on React's runtime. However, if strict purity is desired, pass the schema data as a parameter instead. **Decision: leave as-is for now — flag for future cleanup.**

---

## Task 12: Wave 3 — repository

**Files to move from domain/ to ui/queries/:**
- `domain/get-repository-group.query.ts` → `ui/queries/get-repository-group.query.ts`
- `domain/check-connectivity.mutation.ts` → `ui/queries/check-connectivity.mutation.ts`
- `domain/import-current-commit.mutation.ts` → `ui/queries/import-current-commit.mutation.ts`
- `domain/reimport-last-commit.mutation.ts` → `ui/queries/reimport-last-commit.mutation.ts`

Follow the standard migration recipe.

Note: `get-repository-group.query.ts` uses `useCurrentBranch` and imports `relationshipsQueryKeys` from nodes/relationships — cross-entity dependency stays as-is.

---

## Task 13: Wave 3 — resource-manager

**Files to move from domain/ to ui/queries/:**
- `domain/resource-manager.query-keys.ts` → `ui/queries/resource-manager.query-keys.ts`
- `domain/get-number-pools.query.ts` → `ui/queries/get-number-pools.query.ts`
- `domain/get-pool-utilization.query.ts` → `ui/queries/get-pool-utilization.query.ts`
- `domain/get-resource-allocated.query.ts` → `ui/queries/get-resource-allocated.query.ts`
- `domain/allocate-resource.mutation.ts` → `ui/queries/allocate-resource.mutation.ts`

Follow the standard migration recipe.

Note: `allocate-resource-from-api.ts` in api/ uses `gql` + `jsonToGraphQLQuery` (dynamic mutation name per resource type). This legacy api pattern is out of scope — it stays as-is.

---

## Task 14: Wave 3 — tasks

**Files to move from domain/ to ui/queries/:**
- `domain/tasks.query-keys.ts` → `ui/queries/tasks.query-keys.ts`
- `domain/is-task-running-on-branch/is-task-running-on-branch.query.ts` → `ui/queries/is-task-running-on-branch.query.ts`
- `domain/get-node-task-count/get-task-count.query.ts` → `ui/queries/get-task-count.query.ts`
- `domain/get-task-list/get-task-list.query.ts` → `ui/queries/get-task-list.query.ts`
- `domain/get-tasks-homepage/get-tasks-homepage.query.ts` → `ui/queries/get-tasks-homepage.query.ts`

Follow the standard migration recipe.

Note: Domain functions are in subdirectories (`get-task-list/get-task-list.ts`). The domain async functions stay in their current subdirectories — only the `.query.ts` files move to `ui/queries/` (flattened, no subdirectories in queries/).

Legacy items in ui/ (`task-display.tsx`, `task-item-details.tsx` using old Apollo `useQuery`) — out of scope for this task. Flag for Wave 8 cleanup.

---

## Task 15: Wave 3 — permission

**Files to move from domain/ to ui/queries/:**
- `domain/get-object-permissions.query.ts` → `ui/queries/get-object-permissions.query.ts`

**Additional cleanup:**
- Delete `queries/` directory (`queries/getObjectPermissions.ts`) — this legacy file is consumed only by `api/get-permissions-from-api.ts` and should be inlined there. Move the `getObjectPermissionsQuery` function into `api/get-permissions-from-api.ts`.

Follow the standard migration recipe.

Note: `get-object-permissions.query.ts` imports `useAuth` from `authentication/ui/` — stays in ui/.

---

## Task 16: Wave 4 — IPAM (all sub-entities)

**Files to move — ip-addresses:**
- `ip-addresses/domain/get-ip-address-list.query.ts` → `ip-addresses/ui/queries/get-ip-address-list.query.ts`
- `ip-addresses/domain/get-next-ip-address-available.query.ts` → `ip-addresses/ui/queries/get-next-ip-address-available.query.ts`

**Files to move — ip-namespaces:**
- `ip-namespaces/domain/get-ip-namespace-list.query.ts` → `ip-namespaces/ui/queries/get-ip-namespace-list.query.ts`

**Files to move — ip-prefixes:**
- `ip-prefixes/domain/get-ip-prefix-list.query.ts` → `ip-prefixes/ui/queries/get-ip-prefix-list.query.ts`
- `ip-prefixes/domain/get-next-ip-prefix-available.query.ts` → `ip-prefixes/ui/queries/get-next-ip-prefix-available.query.ts`

**Files to move — ipam-tree:**
- `ipam-tree/domain/get-ipam-tree-nodes-by-parent.query.ts` → `ipam-tree/ui/queries/get-ipam-tree-nodes-by-parent.query.ts`

**Additional cleanup:**
- Move `ip-namespaces/ip-namespace-selector.tsx` → `ip-namespaces/ui/ip-namespace-selector.tsx`

Create `ui/queries/` directories for each sub-entity. Follow the standard migration recipe.

All IPAM query hooks use `useCurrentBranch` + `useAtomValue` + `useObjectsCount` — all stay in ui/.

Note: IPAM query hooks import `objectQueryKeys` from `nodes/object/domain/` — this path will change in Wave 7. Use the current path and update in Wave 7.

**Commit all four sub-entities together:**

```bash
git commit -m "refactor(ipam): migrate all sub-entities to layered architecture"
```

---

## Task 17: Wave 5 — nodes/convert

**Files to move:**
- `convert/domain/get-object-convert-fields-mapping.query.ts` → `convert/ui/queries/get-object-convert-fields-mapping.query.ts`
- `convert/domain/convert-object.mutation.ts` → `convert/ui/queries/convert-object.mutation.ts`

Follow the standard migration recipe.

---

## Task 18: Wave 5 — nodes/hierarchy

**Files to move:**
- `hierarchy/domain/get-object-ancestors.query.ts` → `hierarchy/ui/queries/get-object-ancestors.query.ts`
- `hierarchy/domain/get-tree-nodes-by-parent.query.ts` → `hierarchy/ui/queries/get-tree-nodes-by-parent.query.ts`

Follow the standard migration recipe.

---

## Task 19: Wave 5 — nodes/profiles

**Files to move:**
- `profiles/domain/get-profiles.query.ts` → `profiles/ui/queries/get-profiles.query.ts`

Note: `profiles/` has no `ui/` directory. Create `profiles/ui/queries/`.

Follow the standard migration recipe.

---

## Task 20: Wave 5 — nodes/relationships

**Files to move:**
- `relationships/domain/relationships.query-keys.ts` → `relationships/ui/queries/relationships.query-keys.ts`
- `relationships/domain/get-default-parent.query.ts` → `relationships/ui/queries/get-default-parent.query.ts`
- `relationships/domain/get-relationships/get-relationships.query.ts` → `relationships/ui/queries/get-relationships.query.ts`
- `relationships/domain/get-relationship-count/get-relationship-count.query.ts` → `relationships/ui/queries/get-relationship-count.query.ts`
- `relationships/domain/get-relationship-properties/get-relationship-properties.query.ts` → `relationships/ui/queries/get-relationship-properties.query.ts`
- `relationships/domain/add-relationships/add-relationships.mutation.ts` → `relationships/ui/queries/add-relationships.mutation.ts`
- `relationships/domain/remove-relationships/remove-relationships.mutation.ts` → `relationships/ui/queries/remove-relationships.mutation.ts`

Create `relationships/ui/queries/` directory.

Note: `get-default-parent.query.ts` uses `useCurrentFormContext()` — a React hook. Stays in ui/.

Follow the standard migration recipe.

---

## Task 21: Wave 5 — nodes root-level cleanup

**Files to reorganize:**

| Current | Target | Reason |
|---------|--------|--------|
| `nodes/getObjectItemDisplayValue.tsx` | `nodes/object/ui/object-item-display-value.tsx` | React component belongs in ui/ |
| `nodes/api/getRelationshipParent.ts` | `nodes/relationships/api/get-relationship-parent-from-api.ts` | Belongs with relationships |
| `nodes/api/updateObjectWithId.ts` | `nodes/object/api/update-object-with-id-from-api.ts` | Belongs with object mutations |
| `nodes/api/generateRelationshipListQuery.ts` | `nodes/relationships/api/generate-relationship-list-query-from-api.ts` | Belongs with relationships |
| `nodes/api/getObjectDisplayLabel.ts` | `nodes/object/api/get-object-display-label-from-api.ts` | Merge with existing `get-display-label.ts` if duplicate |
| `nodes/stores/showMetaEdit.atom.ts` | `nodes/object/stores/show-meta-edit.atom.ts` | Scoped to object editing |
| `nodes/edit-form-hook/dynamic-control-types.ts` | `shared/components/form/types/dynamic-control-types.ts` | Generic form types |
| `nodes/edit-form-hook/form.tsx` | `shared/components/form/types/form-field-error.ts` | Single type export |

**Keep at nodes/ root:**
- `nodes/types.ts` — shared by all sub-entities, stays
- `nodes/utils.ts` — cross-entity routing helper, stays

**Flat directories to reorganize:**

| Current | Target |
|---------|--------|
| `nodes/object-item-meta-edit/` | `nodes/object/ui/meta-edit/` |
| `nodes/object-item-details/action-buttons/` | `nodes/object/ui/object-details/action-buttons/` |
| `nodes/object-item-edit/` | `nodes/object/ui/object-edit/` |
| `nodes/object-items/getSchemaObjectColumns.ts` | `nodes/object/utils/get-schema-object-columns.ts` |
| `nodes/object-template/` | `nodes/object/ui/object-template/` |

This is a large reorganization. Update all imports after each move. Run tests frequently.

```bash
git commit -m "refactor(nodes): reorganize root-level files into sub-entities"
```

---

## Task 22: Wave 6 — groups

**Current state:** No domain/ layer. UI uses Apollo `useQuery`/`useMutation` directly with Handlebars templates.

**Step 1: Create domain/ layer**

Create `domain/get-groups.ts`:
```ts
import { getGroupsFromApi } from "@/entities/groups/api/get-groups-from-api";

export interface GetGroupsParams {
  branchName: string;
  atDate?: string;
  objectKind: string;
  objectId: string;
}

export async function getGroups(params: GetGroupsParams) {
  return getGroupsFromApi(params);
}
```

**Step 2: Wrap the Handlebars api in a function**

Rename `api/getGroups.ts` → `api/get-groups-from-api.ts`. Wrap the Handlebars template + `graphqlClient.query()` in an async function that takes typed params.

**Step 3: Create ui/queries/**

Create `ui/queries/get-groups.query.ts` with queryOptions + `useGetGroups` hook.

**Step 4: Create domain for mutations**

Rename `api/updateGroupsQuery.ts` → `api/update-groups-from-api.ts`. Create `domain/update-groups.ts` + `ui/queries/update-groups.mutation.ts`.

**Step 5: Update ui/ components**

Replace direct Apollo usage in `groups-manager.tsx` and `add-group-form.tsx` with the new TanStack hooks.

Replace `graphqlClient.refetchQueries({ include: ["GET_GROUPS"] })` in `object-groups-list.tsx` with `queryClient.invalidateQueries({ queryKey: groupsQueryKeys.all })`.

**Step 6: Verify and test**

```bash
npm run test && npm run build
```

**Step 7: Commit**

```bash
git commit -m "refactor(groups): add domain layer, migrate from Apollo to TanStack Query"
```

---

## Task 23: Wave 6 — role-manager

**Current state:** No domain/ layer. 6 api files export gql.tada DocumentNodes. 5 ui screens use Apollo `useQuery` directly.

**Step 1: Create domain/ layer**

For each of the 6 api files, create a domain async function:
- `domain/get-accounts.ts` — calls `api/getAccounts.ts` DocumentNode via `graphqlClient.query()`
- `domain/get-counts.ts`
- `domain/get-global-permissions.ts`
- `domain/get-groups.ts`
- `domain/get-object-permissions.ts`
- `domain/get-roles.ts`

**Step 2: Rename api files to kebab-case**

- `api/getAccounts.ts` → `api/get-accounts-from-api.ts`
- `api/getCounts.ts` → `api/get-counts-from-api.ts`
- etc.

Wrap each in an async function instead of just exporting a DocumentNode.

**Step 3: Create ui/queries/**

For each domain function, create a query file in `ui/queries/`:
- `ui/queries/get-accounts.query.ts` — queryOptions + `useGetAccounts` hook
- etc.

Create `ui/queries/role-manager.query-keys.ts`.

**Step 4: Update ui/ components**

Replace Apollo `useQuery` imports with new TanStack hooks in:
- `accounts.tsx`
- `groups.tsx`
- `roles.tsx`
- `global-permissions.tsx`
- `object-permissions.tsx`

Replace `graphqlClient.refetchQueries({ include: [...] })` with `queryClient.invalidateQueries(...)`.

**Step 5: Verify, test, commit**

```bash
npm run test && npm run build
git commit -m "refactor(role-manager): add domain layer, migrate from Apollo to TanStack Query"
```

---

## Task 24: Wave 6 — diff

**Current state:** Has api/domain/ui but `checks/` and `node-diff/` directories sit at entity root (outside ui/).

**Step 1: Move checks/ and node-diff/ under ui/**

- `checks/` → `ui/checks/`
- `node-diff/` → `ui/node-diff/`

Update all imports.

**Step 2: Move query/mutation files**

- `domain/diff.query-keys.ts` → `ui/queries/diff.query-keys.ts`
- `domain/get-artifacts-diff.query.ts` → `ui/queries/get-artifacts-diff.query.ts`
- `domain/get-check-details.query.ts` → `ui/queries/get-check-details.query.ts`
- `domain/get-diff-summary.query.ts` → `ui/queries/get-diff-summary.query.ts`
- `domain/get-file.query.ts` → `ui/queries/get-file.query.ts`
- `domain/get-files-diff.query.ts` → `ui/queries/get-files-diff.query.ts`
- `domain/get-validators.query.ts` → `ui/queries/get-validators.query.ts`
- `domain/resolve-conflict.mutation.ts` → `ui/queries/resolve-conflict.mutation.ts`
- `domain/run-check.mutation.ts` → `ui/queries/run-check.mutation.ts`
- `domain/update-diff.mutation.ts` → `ui/queries/update-diff.mutation.ts`

**Step 3: Fix get-diff-tree.ts anomaly**

`domain/get-diff-tree.ts` combines the domain function AND query options in one file. Split:
- Keep `getDiffTree` async function in `domain/get-diff-tree.ts`
- Extract `getDiffTreeInfiniteQueryOptions` + `useDiffTreeInfiniteQuery` to `ui/queries/get-diff-tree.query.ts`

**Step 4: Handle legacy api file**

`api/getValidatorDetails.ts` uses Handlebars — out of scope for structural migration. Rename to `api/get-validator-details-from-api.ts` for naming consistency.

**Step 5: Move utils.tsx to ui/**

`utils.tsx` at entity root contains React components (JSX). Move to `ui/diff-utils.tsx`.

**Step 6: Verify, test, commit**

```bash
npm run test && npm run build
git commit -m "refactor(diff): restructure directories, migrate query layer"
```

---

## Task 25: Wave 6 — triggers

**Current state:** Only `constants.ts` + 2 UI components. No api/ or domain/ layers.

**Step 1: Assess necessity**

The two UI components use:
- `useGetObject` from nodes/object (reads)
- `useCreateObjectMutation` from nodes/object (creates)
- Direct `graphqlClient.mutate()` for updates

triggers/ has no entity-specific data fetching. The only migration needed:

**Step 2: Replace direct graphqlClient.mutate calls**

In `node-attribute-match-form.tsx` and `node-relationship-match-form.tsx`, replace the raw `graphqlClient.mutate()` + `gql(updateObjectWithId(...))` pattern with `useUpdateObjectMutation` from `nodes/object/ui/queries/`.

This depends on nodes/object being migrated (Wave 7). **Defer to Wave 8 or do after Wave 7.**

**Step 3: Commit**

```bash
git commit -m "refactor(triggers): replace direct Apollo mutation with domain hook"
```

---

## Task 26: Wave 6 — proposed-changes

**Current state:** Domain layer exists and is on TanStack Query. Legacy: 4 Handlebars api files, 1 bare DocumentNode export, Jotai atom with `any` type.

**Step 1: Move query/mutation files**

- `domain/proposed-changes.query-keys.ts` → `ui/queries/proposed-changes.query-keys.ts`
- `domain/get-proposed-changes.query.ts` → `ui/queries/get-proposed-changes.query.ts`
- `domain/get-proposed-change-details.query.ts` → `ui/queries/get-proposed-change-details.query.ts`
- `domain/get-proposed-change-thread.query.ts` → `ui/queries/get-proposed-change-thread.query.ts`
- `domain/get-proposed-changes-counts.query.ts` → `ui/queries/get-proposed-changes-counts.query.ts`
- `domain/get-proposed-change-available-actions.query.ts` → `ui/queries/get-proposed-change-available-actions.query.ts`
- `domain/update-review.mutation.ts` → `ui/queries/update-review.mutation.ts`

**Step 2: Rename legacy api files**

- `api/createProposedChange.ts` → `api/create-proposed-change-from-api.ts` (wrap in async function)
- `api/updateProposedChangeReviewFromApi.ts` → `api/update-proposed-change-review-from-api.ts`

The 4 Handlebars files (`getProposedChangesFilesThreads.ts`, etc.) — rename to kebab-case for consistency but leave the Handlebars pattern. Out of scope for full rewrite.

**Step 3: Verify, test, commit**

```bash
npm run test && npm run build
git commit -m "refactor(proposed-changes): migrate query layer, rename legacy api files"
```

---

## Task 27: Wave 7 — nodes/object (Part 1: query layer migration)

**Step 1: Create ui/queries/**

```bash
mkdir -p src/entities/nodes/object/ui/queries
```

**Step 2: Move query key file**

`domain/object.query-keys.ts` → `ui/queries/object.query-keys.ts`

This is the most impactful move — `objectQueryKeys` is imported by many other entities (ipam, tasks, proposed-changes, relationships, object-file). **Update ALL cross-entity imports.**

```bash
grep -r "object/domain/object.query-keys" src/ --include="*.ts" --include="*.tsx" -l
```

**Step 3: Move query files**

- `domain/get-objects.query.ts` → `ui/queries/get-objects.query.ts`
- `domain/get-objects-count.query.ts` → `ui/queries/get-objects-count.query.ts`
- `domain/get-object.query.ts` → `ui/queries/get-object.query.ts`
- `domain/get-node-metadata.query.ts` → `ui/queries/get-node-metadata.query.ts`

**Step 4: Move mutation files**

- `domain/create-object.mutation.ts` → `ui/queries/create-object.mutation.ts`
- `domain/update-object.mutation.ts` → `ui/queries/update-object.mutation.ts`
- `domain/delete-object.mutation.ts` → `ui/queries/delete-object.mutation.ts`
- `domain/delete-objects.mutation.ts` → `ui/queries/delete-objects.mutation.ts`

**Step 5: Fix anomalous api/get-display-label.query.ts**

Move `api/get-display-label.query.ts` → `ui/queries/get-display-label.query.ts` (it's a query hook file misplaced in api/).

**Step 6: Update all imports and test**

This will have the most import updates of any task — objectQueryKeys is referenced across the entire codebase.

```bash
npm run test && npm run build
git commit -m "refactor(nodes/object): migrate query and mutation files to ui/queries"
```

---

## Task 28: Wave 7 — nodes/object (Part 2: domain/api separation)

**Step 1: Create get-objects-from-api.ts**

Extract the query-building and execution logic from `domain/get-objects.ts` into `api/get-objects-from-api.ts`:

```ts
// api/get-objects-from-api.ts
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export async function getObjectsFromApi(params: {
  kind: string;
  attributes: string[];
  relationships: string[];
  filters: Record<string, unknown>;
  branchName: string;
  atDate?: string;
  offset?: number;
  limit?: number;
}) {
  // Move the jsonToGraphQLQuery construction here
  // Move the graphqlClient.query() call here
  // Return raw response
}
```

**Step 2: Simplify domain/get-objects.ts**

`domain/get-objects.ts` should now only:
1. Call `getObjectsFromApi()`
2. Extract and return `data[kind].edges.map(e => e.node)`

Remove all `gql`, `jsonToGraphQLQuery`, and `graphqlClient` imports from domain/.

**Step 3: Repeat for get-object.ts**

Same extraction for the single-object fetch: move query building + execution to `api/get-object-from-api.ts`, simplify `domain/get-object.ts`.

**Step 4: Verify domain/ is clean**

```bash
grep -r "graphqlClient" src/entities/nodes/object/domain/ --include="*.ts"
grep -r "jsonToGraphQLQuery" src/entities/nodes/object/domain/ --include="*.ts"
grep -r "from \"@apollo" src/entities/nodes/object/domain/ --include="*.ts"
```

Expected: zero matches.

**Step 5: Test and commit**

```bash
npm run test && npm run build
git commit -m "refactor(nodes/object): extract query building from domain to api layer"
```

---

## Task 29: Wave 8 — Cleanup

**Step 1: Check if shared/api/graphql/useQuery.ts is still used**

```bash
grep -r "shared/api/graphql/useQuery" src/ --include="*.ts" --include="*.tsx" -l
```

If zero results, delete it. If still referenced (likely by tasks/ui/ and other legacy components), document remaining consumers.

**Step 2: Audit cross-entity imports**

Verify no entity's ui/ or api/ is imported by another entity (only domain/ cross-imports are allowed):

```bash
# Find violations: importing from another entity's api/
grep -r "entities/[^/]*/api/" src/entities/ --include="*.ts" --include="*.tsx" | grep -v "from.*@/entities/\(.*\)/api/" | head -20

# Better: for each entity, check if its api/ is imported from outside
for entity in artifacts authentication branches config diff events generators graphql groups homepage ipam navigation nodes object-file permission proposed-changes repository resource-manager role-manager schema tasks triggers user-profile; do
  echo "=== $entity api/ imported from outside ==="
  grep -r "entities/$entity/api/" src/entities/ --include="*.ts" --include="*.tsx" -l | grep -v "entities/$entity/"
done
```

Fix any violations found.

**Step 3: Final documentation pass**

Review and update:
- `dev/knowledge/frontend/entities-structure.md` — ensure it matches final state
- `dev/guidelines/frontend/naming-conventions.md` — ensure all new suffixes documented
- `frontend/app/AGENTS.md` — update if needed

**Step 4: Commit**

```bash
git commit -m "refactor: complete frontend layered architecture migration cleanup"
```

---

## Dependency Graph

```
Task 1 (docs) ─────────────────────────────────────────────────────────┐
Task 2 (branches) ─────┬───────────────────────────────────────────────┤
Tasks 3-8 (wave 2) ────┤                                               │
Tasks 9-15 (wave 3) ───┤                                               │
Task 16 (ipam) ─────────┤                                               │
Tasks 17-21 (wave 5) ──┤                                               │
Tasks 22-26 (wave 6) ──┤                                               │
Tasks 27-28 (wave 7) ──┤                                               │
Task 29 (cleanup) ──────┘───────────────────────────────────────────────┘
```

Tasks 1-2 must be done first. All subsequent tasks can be done in any order (they are independent PRs), though the numbered order minimizes import churn since earlier waves have fewer cross-entity dependencies.

The one hard dependency: **Task 25 (triggers)** should be done after **Task 27 (nodes/object Part 1)** since triggers needs the migrated update mutation hook.
