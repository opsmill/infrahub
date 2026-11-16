# Page Architecture

> Part of: `dev/guidelines/frontend/`

Rules for structuring page components and the forms / panels they contain. These exist because a recent feature shipped a 500+ line page that owned URL sync, clipboard helpers, formatters, mode routing, and rendering simultaneously, and duplicated `useState` between the page and its selector subcomponents.

## State ownership

Every piece of state has exactly one owner, placed as close as possible to where the state is used. Never duplicate it.

| State | Owner | Mechanism |
|---|---|---|
| Describes what is on screen and should travel with a link (filters, current selection, mode) | The URL | A named hook over `useFilters` or `nuqs` |
| Form fields (in-flight edits before submit) | Form | `react-hook-form` `useForm` |
| Server data | TanStack Query cache | `ui/queries/*.query.ts` |
| Personal preference for this browser (theme, sidebar state) | `localStorage` | `useLocalStorage` or `atomWithStorage` |
| Personal preference that follows the account to other devices (date format, time zone) | Server-side user preferences | `entities/preferences` |
| Other cross-page state | Jotai atoms | `shared/stores/` or `entities/*/stores.ts` |
| Local UI state (open/closed, hover) | Component | `useState` |

### Forbidden patterns

- **Page `useState` shadowed by selector `useState` for the same field.** Lift to a single owner. If the selector is a form, expose `onSubmit(values)` and let its handler commit the values to the URL.
- **`useEffect` to copy props into local state.** Derive during render or use `defaultValues` on the form.
- **Parsing the same URL param in two places.** Wrap it once in a named hook and call that hook wherever the value is needed.
- **Mirroring state that already has an owner into a second store.** URL state copied into a Jotai atom, or form values copied into a `useState`, gives you two values that can disagree and no way to tell which is current. Pick the owner from the table above and read from it; if you find yourself syncing the copy back, the owner is wrong, not missing.

## Preserved and shared state lives in the URL

Put state in the URL when it describes what is on screen and should travel with a link, so reload, Back and a shared link restore it. If sharing it would override the other person's own setting, it is a preference: your link must not switch a colleague to dark mode. Store preferences as the table above shows.

Read URL state close to where it is used, through a named hook over `useFilters` or `nuqs`. A page may read it when the page itself uses the value. Avoid reading it only to pass it as props through components that just forward it.

```tsx
// ✅ the table uses the filters, so it reads them
function AllocationsTable() {
  const [filters] = useAllocationFilters();
  // ...
}

// ❌ the page reads the filters only to forward them through the card to the table
function PoolPage() {
  const [filters, setFilters] = useAllocationFilters();
  return <AllocationsCard filters={filters} onFiltersChange={setFilters} />;
}
```

## Forms own form state

A form component:

1. Calls `useForm({ defaultValues })` once.
2. Renders fields with `FormField` / `.field.tsx` primitives.
3. Calls `onSubmit(values)` on submit; does not write to the URL itself.
4. Does not mirror its own values into a `useState` — the form is the source of truth.

If the form is also a query builder (e.g. path traversal), its `onSubmit` handler either writes the values to the URL through the hook or directly enables a query.

## Component size budget

Soft budgets, not hard limits. If you cross them, ask whether you have multiple concerns mashed into one file.

| File type | Soft budget | Action when exceeded |
|---|---|---|
| Page component | ~250 lines | Split into mode subtrees or extract panels. |
| Form component | ~300 lines | Extract field groups or move pure helpers to `utils.ts`. |
| Selector / picker | ~200 lines | Check if a shared primitive exists (`PeerInput`, `Combobox`). Reuse first. |
| Generic primitive | ~150 lines | Refactor into composition, not configuration. |

## Pure helpers belong in `utils.ts` and have unit tests

If a function is pure (no React, no fetch), it does not belong in a `.tsx` component file. Move it to the entity's `utils.ts` (or `domain/`) and write a Vitest test.

Examples of helpers that should live in `utils.ts`:

- Formatters (`format*`, `*Preview`)
- Clipboard helpers (`copyAllAsText`, `formatAsText`)
- Mappers between API and UI shapes
- Aggregations (`getKindCounts`, `groupByX`)
- Color/icon resolvers (`getKindColor`, `getKindIcon`)

`dev/guides/frontend/writing-unit-tests.md` covers the test setup.

## Concern separation: the "split when you see it" list

Move these out of the page component the moment you write them:

- Pure formatters → `utils.ts`
- Pure clipboard / text-formatting helpers (`copyAllAsText`, `formatAsText`) → `utils.ts`
- Reading from / writing to the clipboard at runtime → reuse `useCopyToClipboard` (`shared/hooks/useCopyToClipboard.ts`); do **not** call `navigator.clipboard.*` directly or reinvent the "Copied!" feedback state
- API mappers → `domain/`
- React Query hooks → `ui/queries/`
- Subtree-specific UI when modes diverge → separate component (`<PathMode />`, `<ImpactMode />`)

## Component contracts: design for both callers from the start

When two modes/features will share a visualization or panel, design the contract for both *before* shipping the first one. Example: a graph component shipped with `destination` as a required prop; when a second mode arrived without a single destination, the only fix was fabricating a synthetic value — a smell that traces back to the original prop design.

Rule: if a second caller is in the spec at all, the prop API must support it on the first iteration. Make optional what is genuinely optional.

## Backend is authoritative

If the backend already filters, transforms, or defaults something, do not duplicate it on the client. Examples:

- Default namespace exclusions for traversal (Core/Internal/Builtin/Lineage/Profile/Template) are server-side. The client must not maintain a parallel `HIDDEN_NAMESPACES` list.
- Schema kinds and their hidden flags come from `useGetSchema`. Do not hardcode them.
- Sort order, pagination defaults, and access checks belong to the server.

If the client needs to *display* a server-side default, surface it via the API (extend a query or response field) rather than mirroring the constant.

## Pagination and sort-change: know the current tradeoff

Object list sorting today intentionally keeps the pagination offset unchanged when the active sort changes, matching how filter changes already behave. At scale (verified with ~10k rows) this produces a page-stitching bug: from a deep offset, changing sort direction shows the tail of the new order immediately followed by rows from the old, now-inconsistent offset. That fix — resetting the offset to its default (`offset: 0`) whenever sort changes — has not landed yet.

For any *new* offset-paginated list that supports both sorting and pagination, prefer resetting the offset to its default value on sort change rather than repeating this known tradeoff.

## Anti-patterns observed in past PRs

| Anti-pattern | Replacement |
|---|---|
| 500+ line page mixing URL sync, formatters, clipboard, modes, rendering | Split into mode components + `utils.ts` + dedicated form |
| Two selectors each owning a copy of the same `sourceId/maxDepth/...` via `useState` | Single form (or controlled inputs from page); no `useState` mirror |
| Mapper fabricating a synthetic destination to satisfy a required prop | Make the prop optional on the visualization API |
| Two selectors with ~50% duplicated UI | Extract a `KindMultiSelect` / shared block once both exist |
| Hand-rolling `gql` + `graphqlClient.query` in a `ui/` file | Use the entity layer (`useGetObject`, `ui/queries/`) |
| Hardcoding `HIDDEN_NAMESPACES` on the client | Backend-authoritative; surface via schema if needed |
| Sort change preserving pagination offset at scale — page-stitching bug, fix not yet landed | Reset the offset to its default (`0`) on sort change, once implemented |

## See also

- `dev/knowledge/frontend/entities-structure.md` — three-layer api/domain/ui architecture
- `dev/knowledge/frontend/shared-components.md` — reuse-first inventory
- `dev/guidelines/frontend/component-patterns.md` — early returns and layout extraction
- `dev/guidelines/frontend/object-forms.md` — form field patterns and `react-hook-form` usage
