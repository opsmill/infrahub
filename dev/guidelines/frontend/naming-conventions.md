# File Naming Conventions

> Part of: `dev/guidelines/frontend/`

## File Suffixes

| Suffix | Purpose | Location | Example |
|--------|---------|----------|---------|
| `.tsx` | React component | ui/ or shared/components/ | `user-profile.tsx` |
| `.ts` | TypeScript module | any | `format-date.ts` |
| `.field.tsx` | Form field component | shared/components/form/fields/ | `input.field.tsx` |
| `.atom.ts` | Jotai atom | shared/stores/ | `time.atom.ts` |
| `.types.ts` | Domain types | domain/ | `branch.types.ts` |
| `.mappers.ts` | Transform functions (optional) | domain/ | `branch.mappers.ts` |
| `.query.ts` | queryOptions + useQuery hook | ui/queries/ | `get-branches.query.ts` |
| `.mutation.ts` | useMutation hook | ui/queries/ | `create-branch.mutation.ts` |
| `.query-keys.ts` | Query key factory | ui/queries/ | `branch.query-keys.ts` |
| `.test.ts(x)` | Test (colocated) | any | `button.test.tsx` |
| `.generated.ts` | Auto-generated | generated/ | `types.generated.ts` |

## Directory Patterns

| Directory | Pattern | Example |
|-----------|---------|---------|
| `shared/components/` | `kebab-case.tsx` | `button.tsx` |
| `shared/components/form/fields/` | `kebab-case.field.tsx` | `input.field.tsx` |
| `shared/hooks/` | `useCamelCase.ts` | `useDebounce.ts` |
| `shared/stores/` | `kebab-case.atom.ts` | `time.atom.ts` |
| `entities/{name}/api/` | `verb-noun-from-api.ts` | `get-branches-from-api.ts` |
| `entities/{name}/domain/` | `verb-noun.ts` | `get-branches.ts` |
| `entities/{name}/domain/` | `{noun}.types.ts` | `branch.types.ts` |
| `entities/{name}/domain/` | `{noun}.mappers.ts` (optional) | `branch.mappers.ts` |
| `entities/{name}/ui/queries/` | `verb-noun.query.ts` | `get-branches.query.ts` |
| `entities/{name}/ui/queries/` | `verb-noun.mutation.ts` | `create-branch.mutation.ts` |
| `entities/{name}/ui/queries/` | `{noun}.query-keys.ts` | `branch.query-keys.ts` |
| `entities/{name}/ui/` | `kebab-case.tsx` | `branches-table.tsx` |
| `pages/` | `kebab-case.tsx` | `login.tsx` |

## Rules

- All files: `kebab-case`
- Tests: colocate with source, never in `__tests__/`
- Types: `{noun}.types.ts` in entity `domain/`, or inline in component
- Avoid `index.ts` barrel exports; prefer direct imports

## Query Keys

Build query keys from a single object, not positional spreads. Object-shaped keys are easier to read in devtools, easier to invalidate by partial match, and easier to diff.

```ts
// ✅ Good
export const pathTraversalKeys = {
  all: ["path-traversal"] as const,
  traverse: (params: { sourceId: string; destinationId: string; maxDepth: number }) =>
    [...pathTraversalKeys.all, "traverse", params] as const,
};

// ❌ Bad: positional spread
traverse: (sourceId, destinationId, maxDepth) =>
  [...pathTraversalKeys.all, "traverse", sourceId, destinationId, maxDepth] as const,
```

Partial invalidation works naturally with the object form: `queryClient.invalidateQueries({ queryKey: pathTraversalKeys.all })`.

## Mutation Invalidation

**Invalidation lives in the mutation hook, not at the callsite.** Co-locating `onSuccess`/`onSettled` with the `useMutation` makes the cache contract auditable — every callsite gets it for free, and you can grep for missing invalidations in CI.

```ts
// ✅ Good — invalidation in the hook
export function useMergeBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: mergeBranch,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
}
```

Use callsite-level invalidation **only** when the queryKey depends on context the hook does not have (e.g., the conflict resolution mutation needs the proposed-change id from the page it is rendered on). When you make that choice, leave a top-of-file comment containing the literal phrase `invalidation-at-callsite` so the audit script below stays green:

```ts
// invalidation-at-callsite: callers pass an explicit `onSuccess` because
// the queryKey depends on the proposed change being viewed.
```

For mutations that genuinely don't change any cached server state (e.g., a connectivity probe), use the same comment and explain why.

### Audit

Every `.mutation.ts` file must contain either `onSuccess`, `onSettled`, or the marker comment:

```bash
for f in $(find frontend/app/src/entities -name '*.mutation.ts'); do
  grep -q 'onSuccess\|onSettled\|invalidation-at-callsite' "$f" || echo "MISSING: $f"
done
```

The output must be empty.

## API files: `*-from-api.ts` / `*.query.ts` / `*.mutation.ts`

Every file under `entities/*/api/` ends in one of:

- `*-from-api.ts` — calls `graphqlClient.query`/`graphqlClient.mutate` (or REST equivalent).
- `*.query.ts` — pure query-string builders (e.g., `jsonToGraphQLQuery`) consumed by an adjacent `*-from-api.ts`.
- `*.mutation.ts` — pure GraphQL mutation literals (rare; usually co-locate with the from-api file instead).

The check is enforced by:

```bash
find frontend/app/src/entities -type f -path '*/api/*.ts' \
  ! -name '*-from-api.ts' ! -name '*.query.ts' ! -name '*.mutation.ts'
```

The output must be empty.
