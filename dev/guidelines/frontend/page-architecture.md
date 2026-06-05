# Page Architecture

> Part of: `dev/guidelines/frontend/`

Rules for structuring page components and the forms / panels they contain. These exist because a recent feature (see PR #9099, path-traversal) shipped a 500+ line page that owned URL sync, clipboard helpers, formatters, mode routing, and rendering simultaneously, and duplicated `useState` between the page and its selector subcomponents.

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

When two modes/features will share a visualization or panel, design the contract for both *before* shipping the first one. Example from PR #9099: a graph component shipped with `destination` as a required prop; when a second mode arrived without a single destination, the only fix was fabricating a synthetic value — a smell that traces back to the original prop design.

Rule: if a second caller is in the spec at all, the prop API must support it on the first iteration. Make optional what is genuinely optional.

## Backend is authoritative

If the backend already filters, transforms, or defaults something, do not duplicate it on the client. Examples:

- Default namespace exclusions for traversal (Core/Internal/Builtin/Lineage/Profile/Template) are server-side. The client must not maintain a parallel `HIDDEN_NAMESPACES` list.
- Schema kinds and their hidden flags come from `useGetSchema`. Do not hardcode them.
- Sort order, pagination defaults, and access checks belong to the server.

If the client needs to *display* a server-side default, surface it via the API (extend a query or response field) rather than mirroring the constant.

## Anti-patterns observed in past PRs

| Anti-pattern | Replacement |
|---|---|
| 500+ line page mixing URL sync, formatters, clipboard, modes, rendering (PR #9099) | Split into mode components + `utils.ts` + dedicated form |
| Two selectors each owning a copy of the same `sourceId/maxDepth/...` via `useState` (PR #9099) | Single form (or controlled inputs from page); no `useState` mirror |
| Mapper fabricating a synthetic destination to satisfy a required prop (PR #9099) | Make the prop optional on the visualization API |
| Two selectors with ~50% duplicated UI | Extract a `KindMultiSelect` / shared block once both exist |
| Hand-rolling `gql` + `graphqlClient.query` in a `ui/` file | Use the entity layer (`useGetObject`, `ui/queries/`) |
| Hardcoding `HIDDEN_NAMESPACES` on the client | Backend-authoritative; surface via schema if needed |

## See also

- `dev/knowledge/frontend/entities-structure.md` — three-layer api/domain/ui architecture
- `dev/knowledge/frontend/shared-components.md` — reuse-first inventory
- `dev/guidelines/frontend/component-patterns.md` — early returns and layout extraction
- `dev/guidelines/frontend/object-forms.md` — form field patterns and `react-hook-form` usage
