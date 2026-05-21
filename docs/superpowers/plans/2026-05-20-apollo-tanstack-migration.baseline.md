# Apollo → TanStack Query Migration — Baseline

Captured **2026-05-20** on branch `ple-tanstack-migration` off `develop`, before any migration work.

## Test status

```text
Test Files  93 passed (93)
Tests       703 passed (703)
Duration    18.67s
```

All unit tests green. The console-error noise during the run is from intentional `throw` cases inside test fixtures (LDAP login collision, etc.), not real failures.

## Production build

`pnpm build` succeeded in 12.30s. Key chunk sizes (gzipped):

| Chunk                                | Raw       | Gzip       |
|--------------------------------------|-----------|------------|
| `index-CfVYkEdJ.js` (main app)       | 3,516.83 kB | **911.79 kB** |
| `graphqlClientApollo-CY-ujpb_.js`    |   199.64 kB | **62.62 kB**  |
| `graphql-BZA3c2f3.js`                |   493.16 kB | 169.39 kB  |
| `editor.api-d4eh2Prr.js` (Monaco)    | 1,848.01 kB | 459.61 kB  |

The `graphqlClientApollo` chunk bundles `@apollo/client` (client + hooks + cache + link infrastructure). Migration target: eliminate the React-hook code (`@apollo/client/react`) once no callers remain, leaving only the transport infrastructure.

## Apollo footprint

```text
rg "from ['\"]@apollo/client" src       → 49 import lines
hook-level imports (useQuery/useMutation/useLazyQuery/useReactiveVar/useSubscription/NetworkStatus) → 12 import lines
```

`gql` template-tag imports across `entities/*/api/` make up the bulk of the remaining 37 lines and stay (per spec).

## Scope discovery during preflight

The plan was built from a `rg "@apollo/client"` audit. That misses **indirect** Apollo-hook consumers — files that import the shared wrapper `src/shared/api/graphql/useQuery.ts` rather than `@apollo/client` directly. Grep on the wrapper:

```text
$ grep -rl "shared/api/graphql/useQuery" src
src/shared/components/ui/id.tsx                                  ← Group 3 (already in plan)
src/shared/components/form/generic-selector.tsx                  ← Group 3 (already in plan)
src/shared/components/inputs/relationship-one.tsx                ← Group 3 (already in plan)
src/shared/components/inputs/enum.tsx                            ← NEW (shared input)
src/shared/components/inputs/dropdown.tsx                        ← NEW (shared input)
src/pages/tasks/task-details.tsx                                 ← NEW (tasks page)
src/entities/tasks/ui/task-display.tsx                           ← NEW (tasks ui)
src/entities/tasks/ui/task-item-details.tsx                      ← NEW (tasks ui)
src/entities/proposed-changes/ui/create-form.tsx                 ← NEW (proposed-changes)
src/entities/proposed-changes/ui/proposed-change-details.tsx     ← NEW (proposed-changes)
src/entities/proposed-changes/ui/proposed-change-edit-trigger.tsx ← Group 4 (already in plan)
src/entities/nodes/object-item-edit/object-item-edit-paginated.tsx ← Group 5 (already in plan)
src/entities/diff/ui/checks/validator-details.tsx                ← NEW (diff)
src/entities/user-profile/ui/tab-update-password.tsx             ← NEW (user-profile)
```

**9 files are not named in the current plan.** They all consume the wrapper, so Task 22 (delete the wrapper) cannot pass until they migrate.

Suggested fold-in (does not change the spec's intent — same target pattern applies):

| File                                                    | Suggested group           |
|---------------------------------------------------------|---------------------------|
| `shared/components/inputs/enum.tsx`                     | Group 3 (shared inputs)   |
| `shared/components/inputs/dropdown.tsx`                 | Group 3 (shared inputs)   |
| `pages/tasks/task-details.tsx`                          | **New Group 4a (tasks)**  |
| `entities/tasks/ui/task-display.tsx`                    | **New Group 4a (tasks)**  |
| `entities/tasks/ui/task-item-details.tsx`               | **New Group 4a (tasks)**  |
| `entities/proposed-changes/ui/create-form.tsx`          | Group 4 (proposed changes)|
| `entities/proposed-changes/ui/proposed-change-details.tsx` | Group 4 (proposed changes)|
| `entities/diff/ui/checks/validator-details.tsx`         | Group 2 (diff readers)    |
| `entities/user-profile/ui/tab-update-password.tsx`      | **New Group 4b (profile)**|

Reviser action required from the human before Group 1 starts — see the message that accompanies this baseline.

## Done-criteria targets

- Hook-level imports: 12 → 0
- Wrapper file: present → deleted
- `index-CfVYkEdJ.js` main chunk: 911.79 kB gzip → target ≤ ~872 kB gzip (~40 kB reduction). Likely smaller — `graphqlClientApollo` chunk should also shrink once `@apollo/client/react` tree-shakes.
- Tests: 93 files / 703 tests passing → same or higher.
- E2E suite: green.
