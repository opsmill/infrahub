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

## URL is the source of truth for shareable state

Anything a user might bookmark, share, or refresh-and-resume (filters, current selection, mode toggle) lives in the URL — not in `useState`. Use `nuqs` for typed URL params, or `useFilters` for the standard filter pattern.

The page component reads URL params and passes them down. Children should not read `searchParams` for state the page already owns. See `dev/guidelines/frontend/page-architecture.md` for the full state-ownership rules.
