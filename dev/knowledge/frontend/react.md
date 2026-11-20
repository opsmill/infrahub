# React

React 19 with React Compiler enabled.

## React Compiler

The compiler automatically memoizes components and values.

**Do NOT use:**

- `memo()`
- `useMemo()`
- `useCallback()`

Write simple code; the compiler optimizes it.

A consequence worth knowing before writing a test: **an assertion that a value keeps its identity
across renders cannot verify a `useMemo`.** The compiler re-adds the memoization, so the test passes
whether or not the hook is there. Mutation-test a stability assertion by removing the thing it claims
to protect; if it still passes, it does not test that thing. Keep identity assertions that cover
behavior other code owns, such as a function that reuses unchanged data across refetches.

## React 19: No forwardRef

`ref` is a regular prop in React 19.

```tsx
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  ref?: React.Ref<HTMLInputElement>;
}

function Input({ ref, ...props }: InputProps) {
  return <input ref={ref} {...props} />;
}
```

## Rules of React

Required for compiler to work:

1. **Components must be pure** - Same inputs = same output, no mutations during render
2. **Hooks at top level only** - No hooks in conditions, loops, or nested functions
3. **Hooks from React functions only** - Components or custom hooks

## Patterns

**Derive state during render** (not with effects):

```tsx
// Do this
const filtered = items.filter(item => item.active);

// Not this
const [filtered, setFiltered] = useState([]);
useEffect(() => setFiltered(items.filter(i => i.active)), [items]);
```

## URL is the source of truth for shareable state

Anything a user might bookmark, share, or refresh-and-resume (filters, current selection, mode toggle) lives in the URL — not in `useState`. Use `nuqs` for typed URL params, or `useFilters` for the standard filter pattern.

The page component reads URL params and passes them down. Children should not read `searchParams` for state the page already owns. See `dev/guidelines/frontend/page-architecture.md` for the full state-ownership rules.

## A failed refetch keeps the previous data — resolve one state, with `error` first

TanStack Query retains the last successful `data` when a background refetch fails, so `data` and
`error` are set at once. A component that derives display booleans from `data` alone then shows a
stale verdict next to its own error treatment. Resolve a single state value in which pending and
error outrank the retained data, and drive every rendered detail from it:

```ts
const state = isPending ? "pending" : error || (data === undefined) ? "check-failed" : data;
```

## A failed next page is not a failed list

An infinite query keeps its loaded pages when `fetchNextPage` fails. Read `isFetchNextPageError` for
that case, not `error`, which a failed background refetch also sets.

- After a failed `fetchNextPage`, render the loaded rows and return the empty or error state only when
  no row is loaded. A failed refetch follows the section above.
- Stop the scroll trigger while `isFetchNextPageError` is set, or it requests the failed page again
  on every scroll.

## Queries do not retry by default

The query client sets `retry: false` app-wide (`shared/api/rest/client.ts`), so do not repeat it in the options of a query. A failed query stays failed until something re-triggers it, unless the query sets its own `retry`, as the repository commits query does (see [repository-commits.md](repository-commits.md)). A 429 load-shed is replayed in the transport below the cache (see `dev/knowledge/frontend/request-priority.md`).

## An effect-driven retry needs a dependency that changes on failure

An effect that launches a must-eventually-succeed step re-runs only when a dependency changes; if every dependency is stable after a failure (same name, same boolean, a stable `refetch`), the step never retries and the screen wedges until reload. Give such an effect a fetch-identity dependency — TanStack Query's `dataUpdatedAt` — so each fresh response re-arms it.
