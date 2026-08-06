# Page Architecture

> Part of: `dev/guidelines/frontend/`

Rules for structuring page components and the forms / panels they contain. These exist because a path-traversal feature page grew to 500+ lines owning URL sync, clipboard helpers, formatters, mode routing, and rendering simultaneously, and duplicated `useState` between the page and its selector subcomponents.

## State ownership

Every piece of state has exactly one owner. When in doubt, push it up; never duplicate.

| State | Owner | Mechanism |
|---|---|---|
| URL-shareable parameters (filters, current selection, mode) | Page | `useFilters` or `nuqs` |
| Form fields (in-flight edits before submit) | Form | `react-hook-form` `useForm` |
| Server data | TanStack Query cache | `ui/queries/*.query.ts` |
| Cross-page global state | Jotai atoms | `shared/stores/` or `entities/*/stores.ts` |
| Local UI state (open/closed, hover) | Component | `useState` |

### Forbidden patterns

- **Page `useState` shadowed by selector `useState` for the same field.** Lift to a single owner. If the selector is a form, expose `onSubmit(values)` and let the page commit the values to the URL.
- **`useEffect` to copy props into local state.** Derive during render or use `defaultValues` on the form.
- **Reading `searchParams` in two places.** One hook call per param, at the page level. Pass values down.
- **Mirroring state that already has an owner into a second store.** URL state copied into a Jotai atom, or form values copied into a `useState`, gives you two values that can disagree and no way to tell which is current. Pick the owner from the table above and read from it; if you find yourself syncing the copy back, the owner is wrong, not missing.

## Pages own URL sync

The page component is the binding layer between the URL and the rest of the tree. It:

1. Reads URL params via `useFilters` / `nuqs`.
2. Decides which mode/sub-tree to render.
3. Passes values to forms as `defaultValues` and to data hooks as query inputs.
4. Receives form submissions and writes back to the URL.

Children should not call `useSearchParams` for state the page already owns.

## Forms own form state

A form component:

1. Calls `useForm({ defaultValues })` once.
2. Renders fields with `FormField` / `.field.tsx` primitives.
3. Calls `onSubmit(values)` on submit; does not write to the URL itself.
4. Does not mirror its own values into a `useState` — the form is the source of truth.

If the form is also a query builder (e.g. path traversal), the page receives submitted values and either updates the URL or directly enables a query.

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

When two modes/features will share a visualization or panel, design the contract for both *before* shipping the first one. For example, a graph component shipped with `destination` as a required prop; when a second mode arrived without a single destination, the only fix was fabricating a synthetic value — a smell that traces back to the original prop design.

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
