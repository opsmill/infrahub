# Frontend review — `infp-1991-graph-path-traversal`

Review of frontend changes on branch `infp-1991-graph-path-traversal` vs `develop`.
Scope: 20 changed files, +5456/-1500 (mostly `package-lock.json`). New feature lives in
`frontend/app/src/entities/path-traversal/` plus a lazy route and a menu link.

## Must fix before merge

### 1. `frontend/app/package.json` has ~25 unrelated downgrades

Appears to be the result of an accidental `npm install` on a different Node/npm setup.
Examples:

- `@tanstack/react-query` `5.90.21 → 5.90.20`
- `graphql` `16.13.1 → 16.12.0`
- `jotai` `2.18.1 → 2.17.1`
- `lucide-react` `0.577 → 0.563`
- `@biomejs/biome` `2.4.6 → 2.3.14`
- `tailwindcss` `4.2.1 → 4.1.18`
- `@tailwindcss/vite` `4.2.1 → 4.1.18`
- `react-resizable-panels` `4.7.2 → 4.6.0`
- `@codemirror/commands` `6.10.2 → 6.10.1`
- `@codemirror/language` `6.12.2 → 6.12.1`
- `@codemirror/view` `6.39.17 → 6.39.12`
- `@vitejs/plugin-react` `5.1.4 → 5.1.3`
- `nuqs` `2.8.9 → 2.8.8`
- `openapi-fetch` `0.17.0 → 0.15.0`
- `react-aria-components` `1.16.0 → 1.15.0`
- `react-error-boundary` `6.1.1 → 6.1.0`
- `react-router` `7.13.1 → 7.13.0`
- `react-scan` `0.5.3 → 0.4.3`
- `react-syntax-highlighter` `16.1.1 → 16.1.0`
- `recharts` `3.8.0 → 3.7.0`
- `remeda` `2.33.6 → 2.33.5`
- `tailwind-merge` `3.5.0 → 3.4.0`
- `vite-tsconfig-paths` `6.1.1 → 6.0.5`
- `@graphql-codegen/cli` `6.1.3 → 6.1.1`
- `@graphql-codegen/typescript` `5.0.9 → 5.0.7`
- `@graphql-codegen/typescript-operations` `5.0.9 → 5.0.7`
- `@types/node` `25.4.0 → 25.2.1`
- `@types/prismjs` `1.26.6 → 1.26.5`
- `@types/react` `19.2.14 → 19.2.13`
- `knip` `5.86.0 → 5.83.0`
- `openapi-typescript` `7.13.0 → 7.10.1`
- `ultracite` `7.2.5 → 7.1.4`

Deps also removed by mistake: `react-scan` (... actually kept, just downgraded), `ts-node`.

The only **intentional new dependencies** for this feature are:

- `@xyflow/react` `^12.10.1` (React Flow graph)
- `dagre` `^0.8.5` (auto layout)
- `@types/dagre` `^0.7.54`

**Action:** rebase on `develop`, restore all other versions, regenerate `package-lock.json`
with a clean `npm install`. This should collapse the lockfile diff from 4656 lines to a
few hundred.

### 2. Raw GraphQL in `object-picker.tsx#resolveUuid` duplicates existing helpers

`resolveUuid(uuid, branchName)` hand-builds a gql string with `jsonToGraphQLQuery` and
calls `graphqlClient.query` directly. The codebase already exposes
`useGetObject({ objectId, objectSchema: { kind: "CoreNode" } })`
(see `frontend/app/src/shared/components/form/fields/peer.field.tsx:28`) which does the
same thing with caching via React Query.

**Action:** replace `resolveUuid` with `useGetObject`.

### 3. `HIDDEN_NAMESPACES` in `utils.ts` duplicates backend filtering

The backend already filters system namespaces for path traversal; hardcoding them again
on the client is drift-prone (if the backend list changes, the UI silently diverges).

**Action:** either remove the client-side filter (backend is authoritative), or surface
the list via schema metadata the client already fetches.

## Simplicity / duplication

### 4. `ObjectPicker` (~219 lines) reimplements `PeerInput`

`frontend/app/src/shared/components/inputs/peer.tsx` already combines:

- `Combobox` trigger,
- `RelationshipComboboxList` (search + pagination against a peer kind),
- `AddRelationshipAction`.

`ObjectPicker` rebuilds the kind combobox, the object combobox, and the wiring between
them. The only genuinely new behavior is the "paste UUID" fallback toggle.

**Action:** wrap `PeerInput` and add a UUID-mode switch beside it. Drop the reinvented
combobox/kind-selector UI.

### 5. State is duplicated between `PathTraversalPage` and the selector components

`path-traversal-page.tsx` keeps `sourceId / destinationId / maxDepth / maxPaths /
kindFilter / excludedKinds` in `useState`. `ObjectSelector` keeps an internal copy of
most of the same fields. They only sync on `handleSearch` submission, so deep-linked URL
params can desync the inner form vs. the outer page.

**Action:** lift state to a single owner — either the page (with selectors as controlled
components) or a single `useForm` at the top. Drop the duplicated `useState` in the
selectors.

### 6. `path-traversal-page.tsx` is 535 lines and mixes concerns

It juggles URL-param sync, mode routing (`path` vs `impact`), clipboard helpers
(`formatPathAsText`, `copyAllPathsAsText`, `pathPreview`, `getKindCounts`), and
rendering.

**Action:**

- Move pure formatters (`formatPathAsText`, `copyAllPathsAsText`, `pathPreview`,
  `getKindCounts`) into `utils.ts` and unit-test them.
- Consider splitting path-mode and impact-mode subtrees into separate components.

### 7. `reachableObjectsToPathResponse` fabricates a synthetic destination

The comment in the file admits it: "Use the first reachable object as a synthetic
destination for the graph." The only reason this exists is that `PathFlowGraph` insists
on a `destination` prop.

**Action:** make `destination` optional on `PathFlowGraph` and render the impact subtree
without it, instead of faking one.

### 8. `ObjectSelector` and `DependencySelector` share ~50% of their UI

Both have source picker, kind list with search, advanced-options block, submit button,
plus the chip-list for selected/excluded kinds.

**Action:** extract `KindMultiSelect` (chip list + searchable combobox) and reuse it in
both; extract the advanced-options block as well.

## Smaller nits

- `path-traversal.query-keys.ts` spreads params positionally into the cache key. A single
  object entry is easier to diff and invalidate.
- `utils.test.ts` only covers `formatRelName` and `getKindColor`.
  `reachableObjectsToPathResponse`, `formatPathAsText`, `copyAllPathsAsText`,
  `pathPreview`, and `getKindCounts` are all pure — add unit tests once they live in
  `utils.ts`.
- `path-traversal.spec.ts` (e2e) checks only static text visibility. Add at least one
  happy-path test: "select a source → submit → graph renders N nodes".
- `object-details-menu.tsx` adds the "Find paths" menu item — LGTM.

## Migrating to shared form fields (`@/shared/components/form`)

**Short answer: don't adopt `DynamicField` / `RelationshipField` directly — reuse the
lower-level inputs (`PeerInput`, `Combobox`, `NodeKindField`) instead.**

### Why the high-level form wrappers don't fit

The shared form stack is schema-driven. `RelationshipField` and `PeerField` require:

1. A `react-hook-form` `Form` context (`useForm()` + `<Form>` wrapper from
   `shared/components/ui/form.tsx`).
2. A `RelationshipSchema` object passed via the `relationship` prop (used for rules,
   cardinality, peer kind, etc.).
3. Values wrapped as
   `FormRelationshipValue = { source: { type: "user" }, value: { id, display_label } }`
   — see `frontend/app/src/shared/components/form/type.ts`.

Path traversal has **none** of those prerequisites:

- No underlying schema relationship (source/destination aren't attributes of a node).
- No write-back mutation — the form is a query builder.
- No pool / template / profile value sources.

Forcing the dynamic-field wrappers would mean fabricating a fake `RelationshipSchema`
and round-tripping every plain string id through a `source`/`value` wrapper. Net
negative in complexity.

### What to reuse instead (primitive inputs)

| Current in path-traversal | Replace with |
| --- | --- |
| `ObjectPicker` kind combobox (`object-picker.tsx:130-180`) | `NodeKindField`'s inner combobox, or extract a `NodeKindSelect` primitive |
| `ObjectPicker` search mode (`object-picker.tsx:180-219`) | `PeerInput` from `shared/components/inputs/peer.tsx` — already contains `RelationshipComboboxList` + `AddRelationshipAction` |
| `ObjectPicker` UUID resolve | `useGetObject({ objectId, objectSchema: { kind: "CoreNode" } })` |
| `ObjectSelector` / `DependencySelector` hand-rolled `useState` + `<form onSubmit>` | `useForm()` + `<Form>` + `FormSubmit`; plain `<input>` → `FormField` + shadcn `Input`; skip `InputField` / `NumberField` from the dynamic form (schema-driven, overkill here) |
| Kind multiselect (excluded / target kinds) | No shared component exists — keep custom, extract into a single `KindMultiSelect` used by both selectors |

### Rough refactor shape if adopted

- Delete `ObjectPicker`'s combobox + search implementation; keep only the UUID-mode
  toggle and delegate the rest to `PeerInput`.
- `ObjectSelector` and `DependencySelector` shrink to ~120 lines each:
  `useForm` + three primitives + shared `KindMultiSelect`.
- `path-traversal-page.tsx` stops mirroring the selectors' state — the form owns form
  state, the page owns URL sync and query-enable.

## Key file references

- `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx` (535 lines)
- `frontend/app/src/entities/path-traversal/ui/object-picker.tsx` (219 lines)
- `frontend/app/src/entities/path-traversal/ui/object-selector.tsx` (294 lines)
- `frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx` (124 lines)
- `frontend/app/src/entities/path-traversal/ui/path-flow-graph.tsx` (367 lines)
- `frontend/app/src/shared/components/inputs/peer.tsx` — `PeerInput`
- `frontend/app/src/shared/components/form/fields/peer.field.tsx` — `PeerField` wrapper
- `frontend/app/src/shared/components/form/type.ts` — `FormRelationshipValue`, `DynamicRelationshipFieldProps`
- `frontend/app/src/shared/components/form/dynamic-form.tsx` — `DynamicField` switch
- `frontend/app/src/shared/components/form/fields/node-kind.field.tsx` — kind selector field
- `frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx` — searchable, paginated list by peer kind

Review dated 2026-04-22.
