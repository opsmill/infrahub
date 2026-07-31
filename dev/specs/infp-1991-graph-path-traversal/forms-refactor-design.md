# Path traversal — forms refactor design

Design for the **forms + page split** slice of the path-traversal frontend
follow-up. Targets review items #5 and #6 from
[`frontend-review.md`](./frontend-review.md), plus the form-fields punch list
and the form-context plumbing recommendations in the same document.

Date: 2026-05-04
Branch: `ple-fields-components`
Scope: frontend-only refactor of `frontend/app/src/entities/path-traversal/`
plus a small generic improvement to
`frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx`.

## Why

The path-traversal feature ships with three tightly coupled forms
(`object-selector.tsx`, `dependency-selector.tsx`, `object-picker.tsx`) and a
535-line page (`path-traversal-page.tsx`) that orchestrates URL params, mode
routing, two queries, four pure formatters, and the result rendering for both
modes.

The forms reimplement primitives the rest of Infrahub already provides:

- Hand-rolled `useState` per field instead of `react-hook-form` (RHF).
- Raw `<input>` / `<button>` / `<label>` instead of `Input` / `Button` /
  `FormLabel`.
- A hand-rolled "Show / Hide Advanced Options" toggle instead of `Accordion`.
- A `mode`-toggle inside `ObjectPicker` that switches between label search
  (via `PeerInput`) and a UUID-paste mode (raw `<input>` + `useGetObject`),
  rather than letting one input handle both.
- `useSearchParams` from react-router instead of `nuqs` (the convention the
  rest of the app has converged on).
- No client-side validation: an empty source silently no-ops on submit.
- State spread across three places per mode (URL, page `useState`, selector
  `useState`), kept in sync by manual reducers.

This design lifts the path-traversal forms onto the shared form/URL/UUID
plumbing without falling into the schema-driven `DynamicField` /
`RelationshipField` wrappers, which the review explicitly opted out of —
those require a `RelationshipSchema` and a `FormRelationshipValue` wrapper
that path traversal has no source for.

## Goals

1. One source of truth per field. URL is canonical; RHF holds in-memory form
   state; the React Query call is enabled by URL completeness. No `useState`
   mirroring across components.
2. Drop hand-rolled inputs in favor of shared primitives: `Form`, `FormField`,
   `FormSubmit`, `FormMessage`, `Input`, `Label`, `Accordion`, `KindMultiSelect`,
   `NodeKindSelect`, `PeerInput`, plus `Button` / `Spinner` from `@infrahub/ui`.
4. Validation surfaces in the UI (red border + `FormMessage`), not silent
   submit-button gating.
5. `path-traversal-page.tsx` shrinks to chrome (header, mode tabs, panel
   slot). Each mode gets its own self-contained folder with form, results,
   and URL hook.
6. Deep-linked URLs auto-run the query on first load (no extra click).
7. Search and UUID lookup happen through the same input, with no toggle.

## Non-goals

The following items from `frontend-review.md` are explicitly **out of scope**
for this refactor and will land in separate PRs:

- **Item #7** — drop the synthetic destination in
  `reachableObjectsToPathResponse` and make `destination` optional on
  `PathFlowGraph`. Touches `path-flow-graph.tsx` rendering; orthogonal to
  forms.
- **Item #9** — refactor `infra-node.tsx` and `schema-viewer.tsx` to use the
  shared `Card` from `@infrahub/ui`. Pure visual refactor.
- **Item #3 (full resolution)** — replace client-side `HIDDEN_NAMESPACES`
  with backend-surfaced schema metadata. Requires backend work; the current
  partial resolution (named helper + drift comment) stays as-is.

In-scope-but-trivial:

- Convert positional cache keys in `path-traversal.query-keys.ts` to an
  object shape (the new form code already calls these keys with the new arg
  layout, so the change costs nothing).

## File layout

```
entities/path-traversal/ui/
├── path-traversal-page.tsx               # ~80 lines, chrome only
├── path-mode/
│   ├── path-mode-panel.tsx               # form + query + results wiring
│   ├── path-mode-form.tsx                # RHF form
│   ├── path-mode-results.tsx             # path picker + flow graph + meta
│   └── use-path-mode-params.ts           # nuqs URL slice
├── dependencies-mode/
│   ├── dependencies-mode-panel.tsx
│   ├── dependencies-mode-form.tsx
│   ├── dependencies-mode-results.tsx
│   └── use-dependencies-mode-params.ts
├── object-picker.tsx                     # ~50 lines, no mode toggle
├── path-flow-graph.tsx                   # unchanged this round
├── infra-node.tsx                        # unchanged this round
├── path-edge.tsx                         # unchanged this round
├── format-paths.ts                       # NEW: pure formatters
├── format-paths.test.ts                  # NEW
├── utils.ts                              # unchanged
└── utils.test.ts                         # unchanged
```

Shared additions outside `path-traversal/`:

- `frontend/app/src/shared/utils/is-uuid.ts` (~5 lines) + `is-uuid.test.ts`.
- `frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx`
  — gains a UUID-detection branch so any caller's search input falls back to
  `filterQuery: { ids: [search] }` when the input is UUID-shaped.

Deletions:

- `entities/path-traversal/ui/object-selector.tsx` — replaced by
  `path-mode/path-mode-form.tsx`.
- `entities/path-traversal/ui/dependency-selector.tsx` — replaced by
  `dependencies-mode/dependencies-mode-form.tsx`.
- The `mode` / `uuidInput` `useState` and the raw `<input>` UUID-paste UI
  inside `object-picker.tsx`.
- The four pure formatters inlined at the top of `path-traversal-page.tsx`
  (`formatPathAsText`, `copyAllPathsAsText`, `pathPreview`, `getKindCounts`).

## Data flow

For each mode panel, four pieces of state interact: URL params, RHF form
state, React Query state, render. URL is canonical:

```
                       ┌──────────────────────────┐
                       │  URL (nuqs)              │
                       │  ?source=...&depth=5     │
                       └──────┬─────────────▲─────┘
                              │             │
              seeds form,     │             │   submit writes
              re-resets via   │             │   submitted values
              RHF `values`    │             │
              prop on change  ▼             │
                       ┌──────────────────────────┐
                       │  RHF form (in-memory)    │
                       │  source, destination,... │
                       └──────┬─────────────▲─────┘
                              │             │
                  on submit:  │             │   user types in fields
                  pass values │             │
                              ▼             │
                       ┌──────────────────────────┐
                       │  React Query             │
                       │  enabled iff URL has     │
                       │  required params         │
                       └──────┬───────────────────┘
                              ▼
                          render results
```

Concrete rules:

1. **URL is canonical.** A `usePathModeParams()` / `useDependenciesModeParams()`
   hook returns `[params, setParams]` from one `useQueryStates(...)` call.
2. **RHF seeds and stays in sync via `values` prop.** `useForm` is given
   both `defaultValues` and `values`, both equal to `paramsToFormValues(params)`.
   When `params` changes (deep equal), RHF auto-resets the form. No
   `useEffect`.
3. **Submit writes URL + runs query.** `onSubmit(values)` calls
   `setParams(formValuesToParams(values))`. The `Form` wrapper already calls
   `currentForm.reset(values)` post-submit, so `formState.isDirty` resets.
4. **Query is enabled iff URL has all required params.**
   `enabled: !!params.source && !!params.destination` for path mode,
   `enabled: !!params.source && params.targetKinds.length > 0` for
   dependencies mode. Deep-linked URLs auto-run with no second click.
5. **Browser back/forward** triggers `useQueryStates` to update params, which
   re-equals the `values` prop on `useForm`, which auto-resets the visible
   form. The query re-fires because its key changed.
6. **Typing in a field does not write the URL.** Only submit does. This
   keeps in-flight queries from firing on every keystroke.

## Path mode form

`path-mode/path-mode-form.tsx`.

```ts
type PathModeFormValues = {
  sourceId: string;            // required
  destinationId: string;       // required
  maxDepth: number;            // 1..20, default 5
  maxPaths: number;            // 1..100, default 10
  kindFilter: string[];        // include-only kinds; empty = no restriction
  excludedKinds: string[];     // exclude-these kinds; empty = exclude none
};
```

Field plumbing:

| Field | UI primitive | RHF rules |
|---|---|---|
| `sourceId` | `FormField` → `ObjectPicker label="Source Object"` | `{ required: "Source is required" }` |
| `destinationId` | `FormField` → `ObjectPicker label="Destination Object"` | `{ required: "Destination is required" }` |
| `maxDepth` | `FormField` → `FormInput` → `Input type="number"` + `FormMessage` | `{ required: true, min: 1, max: 20 }` |
| `maxPaths` | same | `{ required: true, min: 1, max: 100 }` |
| `kindFilter` | `FormField` → `KindMultiSelect filter={isVisibleNamespace}` | none |
| `excludedKinds` | `FormField` → `KindMultiSelect showChips chipTone="red" filter={isVisibleNamespace}` | none |

Layout:

```
<Form form={form} onSubmit={onSubmit}>
  <FormField name="sourceId" ...> <ObjectPicker label="Source Object" .../> </FormField>
  {(sourceId || destinationId) && <Button variant="ghost" onClick={swap}>⇅ Swap</Button>}
  <FormField name="destinationId" ...> <ObjectPicker label="Destination Object" .../> </FormField>

  <Accordion type="single" collapsible>
    <AccordionItem value="advanced">
      <AccordionTrigger>Advanced options</AccordionTrigger>
      <AccordionContent>
        <FormField name="maxDepth" .../>
        <FormField name="maxPaths" .../>
        <FormField name="kindFilter" .../>
        <FormField name="excludedKinds" .../>
      </AccordionContent>
    </AccordionItem>
  </Accordion>

  <FormSubmit isPending={query.isFetching} className="w-full">Find Paths</FormSubmit>
</Form>
```

`FormSubmit isPending={query.isFetching}` keeps the in-button spinner showing
through the network round-trip even after `formState.isSubmitting` flips
back to `false` (which happens immediately, since `onSubmit` only writes URL
and returns).

The swap button uses `form.setValue("sourceId", currentDestination)` and
the inverse, so the form remains in a single transaction.

## Dependencies mode form

`dependencies-mode/dependencies-mode-form.tsx`.

```ts
type DependenciesModeFormValues = {
  sourceId: string;        // required
  targetKinds: string[];   // required, length >= 1
  maxDepth: number;        // 1..20, default 5
};
```

Field plumbing:

| Field | UI primitive | RHF rules |
|---|---|---|
| `sourceId` | `FormField` → `ObjectPicker label="Source Object"` | `{ required: "Source is required" }` |
| `targetKinds` | `FormField` → `KindMultiSelect showChips chipTone="blue" filter={isVisibleNamespace} label="Target kinds"` | `{ validate: (v) => v.length > 0 \|\| "Select at least one target kind" }` |
| `maxDepth` | `FormField` → `Input type="number"` + `FormMessage` | `{ required: true, min: 1, max: 20 }` |

No advanced accordion: only one numeric field, surface it directly.

```
<Form form={form} onSubmit={onSubmit}>
  <FormField name="sourceId" .../>
  <FormField name="targetKinds" .../>
  <FormField name="maxDepth" .../>
  <FormSubmit isPending={query.isFetching} className="w-full">Find Dependencies</FormSubmit>
</Form>
```

The "amber" tint that the today's button uses stays via `className` until/if
`@infrahub/ui`'s `Button` ever grows a tone variant.

## ObjectPicker simplification + UUID search

### `RelationshipComboboxList` UUID auto-detect

`frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx`
— add ~3 lines so the combobox switches to an `ids` filter when the search
input is UUID-shaped:

```ts
import { isUuid } from "@/shared/utils/is-uuid";

const isUuidSearch = search.length > 0 && isUuid(search);
const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
  useRelationships({
    peer,
    search: isUuidSearch ? undefined : search,
    filterQuery: isUuidSearch ? { ids: [search] } : filterQuery,
  });
```

This change benefits every caller of `RelationshipComboboxList` (and
therefore every `PeerInput`). It also documents the intent in one place: an
inline comment notes that an `ids` UUID filter overrides the caller's
`filterQuery` because UUID is a maximally specific match.

### `is-uuid` helper

`frontend/app/src/shared/utils/is-uuid.ts`:

```ts
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const isUuid = (s: string): boolean => UUID_RE.test(s.trim());
```

`is-uuid.test.ts` covers: valid v4, valid mixed-case, missing dashes, empty,
leading/trailing whitespace, prefix/suffix garbage.

### `ObjectPicker` after the change

```ts
type ObjectPickerProps = {
  label: string;
  value: string;                      // id only
  onChange: (id: string) => void;     // id only
};

export function ObjectPicker({ label, value, onChange }: ObjectPickerProps) {
  const [selectedKind, setSelectedKind] = useState<string | null>(null);
  const { data: resolved } = useGetObject(
    { objectId: value, objectSchema: { kind: "CoreNode" } as ModelSchema },
    { enabled: !!value }
  );

  const peerValue: Node | null = value
    ? {
        id: value,
        display_label: resolved?.display_label ?? value,
        __typename: selectedKind ?? "",
      }
    : null;

  return (
    <div className="space-y-1">
      <FormLabel>{label}</FormLabel>
      <NodeKindSelect
        value={selectedKind}
        onChange={setSelectedKind}
        filter={isVisibleNamespace}
      />
      <PeerInput
        peer={selectedKind ?? "CoreNode"}
        value={peerValue}
        onChange={(node) => onChange(node?.id ?? "")}
        placeholder="Search by name, or paste an object ID"
      />
      {value && (
        <Button variant="ghost" size="sm" onClick={() => onChange("")}>
          Clear
        </Button>
      )}
    </div>
  );
}
```

What goes away:

- `mode` `useState` and the toggle button.
- `uuidInput` `useState` and the raw `<input>`.
- `displayLabel` prop (and the parallel `*Label` `useState` it forced into
  every caller).

Open verification during implementation: confirm `peer="CoreNode"` is
accepted by the relationship-list query and returns mixed-kind results when
no kind is picked. If it doesn't, fall back to "kind required for label
search; UUID search via the dropdown still works once the user has clicked
into the combobox" — the toggle stays gone either way, since the UUID path
is now inside `RelationshipComboboxList`, not in `ObjectPicker`.

## URL state hooks

### `path-mode/use-path-mode-params.ts`

```ts
import {
  parseAsArrayOf,
  parseAsInteger,
  parseAsString,
  useQueryStates,
} from "nuqs";

export const PATH_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  destination: parseAsString.withDefault(""),
  depth: parseAsInteger.withDefault(5),
  maxPaths: parseAsInteger.withDefault(10),
  kindFilter: parseAsArrayOf(parseAsString).withDefault([]),
  excludedKinds: parseAsArrayOf(parseAsString).withDefault([]),
  selectedPath: parseAsInteger.withDefault(0),
} as const;

export function usePathModeParams() {
  return useQueryStates(PATH_MODE_PARAMS, { history: "push" });
}
```

### `dependencies-mode/use-dependencies-mode-params.ts`

```ts
export const DEPENDENCIES_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  targetKinds: parseAsArrayOf(parseAsString).withDefault([]),
  depth: parseAsInteger.withDefault(5),
} as const;

export function useDependenciesModeParams() {
  return useQueryStates(DEPENDENCIES_MODE_PARAMS, { history: "push" });
}
```

### Page-level mode toggle

```ts
const [mode, setMode] = useQueryState(
  "mode",
  parseAsStringEnum(["path", "dependencies"]).withDefault("path"),
);
```

### URL ↔ form mapping helpers

Two pure helpers per panel, co-located in the panel file:

```ts
// path-mode-panel.tsx
function paramsToFormValues(p: PathModeParams): PathModeFormValues {
  return {
    sourceId: p.source,
    destinationId: p.destination,
    maxDepth: p.depth,
    maxPaths: p.maxPaths,
    kindFilter: p.kindFilter,
    excludedKinds: p.excludedKinds,
  };
}

function formValuesToParams(v: PathModeFormValues): Partial<PathModeParams> {
  return {
    source: v.sourceId,
    destination: v.destinationId,
    depth: v.maxDepth,
    maxPaths: v.maxPaths,
    kindFilter: v.kindFilter,
    excludedKinds: v.excludedKinds,
    selectedPath: 0, // submit always resets to first path
  };
}
```

### Panel wiring

```ts
export function PathModePanel() {
  const [params, setParams] = usePathModeParams();
  const form = useForm<PathModeFormValues>({
    defaultValues: paramsToFormValues(params),
    values: paramsToFormValues(params),
  });

  const query = useGetPathTraversal(
    {
      sourceId: params.source,
      destinationId: params.destination,
      maxDepth: params.depth,
      maxPaths: params.maxPaths,
      kindFilter: params.kindFilter,
      excludedKinds: params.excludedKinds,
    },
    { enabled: !!params.source && !!params.destination },
  );

  return (
    <SplitLayout>
      <PathModeForm
        form={form}
        onSubmit={(v) => setParams(formValuesToParams(v))}
        isPending={query.isFetching}
      />
      <PathModeResults
        query={query}
        selectedPath={params.selectedPath}
        onSelectPath={(i) => setParams({ selectedPath: i })}
      />
    </SplitLayout>
  );
}
```

Dependencies-mode panel mirrors this shape.

## Pure formatters

`format-paths.ts` — moved verbatim from `path-traversal-page.tsx`:

- `formatPathAsText(data: PathTraversalResponse, pathIndex: number): string`
- `copyAllPathsAsText(data: PathTraversalResponse): string`
- `pathPreview(path: PathResult, maxObjects?: number): string`
- `getKindCounts(path: PathResult): string`

`format-paths.test.ts` covers each: empty input, single-element input,
multi-element input, missing relationship fallback, ellipsis truncation,
ordering of kind counts.

## Cache key shape

`path-traversal.query-keys.ts` — switch positional args to an object:

```ts
// before:
export const pathTraversalKeys = {
  paths: (sourceId, destinationId, maxDepth, maxPaths, kindFilter, excludedKinds, branchName) =>
    ["pathTraversal", "paths", sourceId, destinationId, maxDepth, maxPaths, kindFilter, excludedKinds, branchName],
  // ...
};

// after:
export const pathTraversalKeys = {
  paths: (params: PathTraversalQueryParams & { branchName?: string }) =>
    ["pathTraversal", "paths", params],
  // ...
};
```

Easier to diff and invalidate. Trivial change but the new form code calls
these keys with the new arg shape anyway.

## Testing

### Unit (Vitest)

1. `format-paths.test.ts` — empty path, single-object, multi-hop with
   relationships, missing relationship fallback, `pathPreview` truncation,
   `getKindCounts` ordering.
2. `is-uuid.test.ts` — valid v4, mixed-case, missing dashes, empty,
   whitespace, prefix/suffix garbage.
3. `path-mode-panel` and `dependencies-mode-panel` mapping helpers
   (`paramsToFormValues`, `formValuesToParams`) — pure, trivially testable.
4. `relationship-combobox-list.test.tsx` — assert that typing a UUID
   switches the underlying `useRelationships` call to
   `{ filterQuery: { ids: [...] } }` instead of `{ search }`.

### E2E (Playwright)

Bump `path-traversal.spec.ts` from "static text only" to:

1. Happy path (path mode): seed two known objects, search source by name,
   search destination by name, click "Find Paths", assert ≥ N nodes render
   in the graph.
2. Happy path (dependencies mode): seed source + target kind, run, assert
   reachable list renders.
3. Validation feedback: click "Find Paths" with empty source — assert
   `FormMessage` text "Source is required" is visible and the query did not
   run.
4. Deep link auto-runs: navigate directly to
   `/path-traversal?mode=path&source=<id>&destination=<id>&depth=5&maxPaths=10`,
   assert graph renders without clicking submit.
5. UUID-paste search: open source picker, paste a known UUID into the
   combobox search, pick the result, submit. Validates the
   `RelationshipComboboxList` UUID detection end-to-end.

### Manual UI verification

Before claiming done, in a running dev server:

- Form errors render and clear correctly.
- Browser back/forward updates form fields and re-runs query.
- Switching modes preserves URL params for the inactive mode.

## Sequencing

A reasonable landing order, each commit independently reviewable:

1. Add `is-uuid.ts` + `is-uuid.test.ts`. Add the UUID branch to
   `RelationshipComboboxList` + its test. No path-traversal changes yet.
2. Move pure formatters out of `path-traversal-page.tsx` into
   `format-paths.ts`. Add `format-paths.test.ts`. No behavior change.
3. Replace `object-picker.tsx` with the simplified version (no mode toggle,
   id-only API). Update its three call sites to pass id only.
4. Replace `object-selector.tsx` with `path-mode/`: panel, form, results,
   URL hook. Wire from `path-traversal-page.tsx`.
5. Replace `dependency-selector.tsx` with `dependencies-mode/`: same shape.
6. Shrink `path-traversal-page.tsx` to chrome (header, mode tabs, panel
   slot) once both panels are in place.
7. Convert `path-traversal.query-keys.ts` to object-shaped keys.
8. Add the missing E2E coverage.

Each step keeps the page rendering and the existing E2E "Path Traversal
heading visible" test green.
