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

## A render-time read of mutable global state is frozen at mount

The compiler memoizes a value whose inputs are all non-reactive by computing it on the first render
and never again — its cache slot is guarded by `Symbol.for("react.memo_cache_sentinel")`, and nothing
invalidates that guard. Reading `window.location` or a module-level mutable during render therefore
does not merely risk a stale value, it guarantees one for the life of the mount:

```tsx
// ❌ Impure read, no reactive input — evaluated once, then frozen
<Link to={constructPath("/")} />

// ✅ The hook closes over reactive state, so the call re-evaluates
const constructPath = useConstructPath();
<Link to={constructPath("/")} />
```

Give the component a reactive dependency on whatever the value really derives from — a context
value, a store value, a query result — instead of reaching for the global.

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

## An effect-driven retry needs a dependency that changes on failure

The REST client sets `retry: false` app-wide (`shared/api/rest/client.ts`), so a failed query stays failed until something re-triggers it. An effect that launches a must-eventually-succeed step re-runs only when a dependency changes; if every dependency is stable after a failure (same name, same boolean, a stable `refetch`), the step never retries and the screen wedges until reload. Give such an effect a fetch-identity dependency — TanStack Query's `dataUpdatedAt` — so each fresh response re-arms it.
