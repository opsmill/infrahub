# React

React 19 with React Compiler enabled.

## React Compiler

The compiler automatically memoizes components and values.

**Do NOT use:**
- `memo()`
- `useMemo()`
- `useCallback()`

Write simple code; the compiler optimizes it.

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

**Keeping loaded data across a cold poll.** TanStack's `placeholderData: keepPreviousData` only fills in while `data` is `undefined` after a query-key change. A refetch on the *same* key replaces `data` outright, so a poll that answers "not available yet" blanks a list that was already loaded. Keep the loaded rows inside the query with a `structuralSharing` callback: when the old data holds loaded rows and the new answer is cold, return the old pages with the first page's availability fields (`condition`, `unavailable`, `pending_count`) taken from the new answer, and `replaceEqualDeep(oldData, newData)` otherwise. Returning `oldData` untouched hides the cold answer: no stale notice shows, and `refetchInterval` reads the retained data as available and stops polling. Recording the latest availability keeps the rows on screen, lets the view say they are stale, and keeps polling until a worker answers. Test "old has loaded rows", not "old was available", so a second cold answer still keeps them. Doing it in the query rather than in a component hook keeps `pages`, `pageParams` and `hasNextPage` consistent for every consumer, so paging still works after a cold poll; a key change starts with no `oldData`, so a branch or object switch never shows the old list. `entities/repository/ui/queries/get-repository-commits.query.ts` is the reference.

## URL is the source of truth for shareable state

Anything a user might bookmark, share, or refresh-and-resume (filters, current selection, mode toggle) lives in the URL — not in `useState`. Use `nuqs` for typed URL params, or `useFilters` for the standard filter pattern.

The page component reads URL params and passes them down. Children should not read `searchParams` for state the page already owns. See `dev/guidelines/frontend/page-architecture.md` for the full state-ownership rules.

## An effect-driven retry needs a dependency that changes on failure

The REST client sets `retry: false` app-wide (`shared/api/rest/client.ts`), so a failed query stays failed until something re-triggers it. The one exception is a 429 load-shed, replayed in the transport below the cache (see `dev/knowledge/frontend/request-priority.md`). An effect that launches a must-eventually-succeed step re-runs only when a dependency changes; if every dependency is stable after a failure (same name, same boolean, a stable `refetch`), the step never retries and the screen wedges until reload. Give such an effect a fetch-identity dependency — TanStack Query's `dataUpdatedAt` — so each fresh response re-arms it.
