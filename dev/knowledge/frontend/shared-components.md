# Shared Components Inventory

> Part of: `dev/knowledge/frontend/`

A discovery map of reusable building blocks. **Look here before building a new picker, combobox, kind selector, or form input.** Most "new" UI in this codebase already has a shared primitive — see PR #9099 for an example where a 200+ line custom object picker and a hand-rolled `gql` UUID resolver were written because this map didn't exist.

The dependency rule still applies: `app → pages → entities → shared`. Cross-entity reuse goes through another entity's `domain/` or `ui/` — never `api/`.

## When to use what

### Picking an existing object (single)

| Need | Use | Location |
|------|-----|----------|
| Pick a peer in a form (with `react-hook-form`) | `PeerField` | `shared/components/form/fields/peer.field.tsx` |
| Pick a peer outside a form | `PeerInput` | `shared/components/inputs/peer.tsx` |
| Resolve a single object by UUID | `useGetObject({ objectId, objectSchema })` | `entities/nodes/object/ui/queries/get-object.query.ts` |
| Searchable + paginated list of one peer kind | `RelationshipComboboxList` | `entities/nodes/relationships/ui/relationship-combobox-list.tsx` |
| Hierarchical (parent/child) peer list | `RelationshipHierarchicalComboboxList` | `entities/nodes/relationships/ui/relationship-hierarchical-combobox-list.tsx` |
| Add-relationship action button | `AddRelationshipAction` | `entities/nodes/relationships/ui/add-relationship-action.tsx` |

**Never** hand-build a `gql` query string + `graphqlClient.query` to resolve a single node. That bypasses caching, branch context, and the entity layer. Use `useGetObject`.

### Picking a node kind

| Need | Use | Location |
|------|-----|----------|
| Select a single schema kind | `NodeKindField` | `shared/components/form/fields/node-kind.field.tsx` |
| Multi-select kinds (chips) | None yet — extract one if you need this | Candidate: `shared/components/form/fields/node-kind-multi.field.tsx` |
| Filter system namespaces from a kind list | Use the schema metadata — **do not** hardcode `["Core", "Internal", ...]` on the client; the backend already filters |

### Picking primitive values

| Need | Use | Location |
|------|-----|----------|
| Combobox (single value) | `Combobox` | `shared/components/ui/combobox.tsx` |
| Command palette pattern | `Command` | `shared/components/ui/command.tsx` |
| Dropdown menu | `DropdownMenu` | `shared/components/ui/dropdown-menu.tsx` |
| Date picker | `DatePicker` | `shared/components/inputs/date-picker.tsx` |
| Color picker | `ColorPicker` | `shared/components/inputs/color-picker.tsx` |
| Search input | `SearchInput` | `shared/components/inputs/search-input.tsx` |
| Pool select | `PoolSelect` | `shared/components/inputs/pool-select.tsx` |
| Enum select | `EnumInput` | `shared/components/inputs/enum.tsx` |

### Form fields (`react-hook-form` integration)

All `.field.tsx` files in `shared/components/form/fields/` wrap a primitive in the `{ source, value }` form-value structure documented in `dev/guidelines/frontend/object-forms.md`.

| Field | Purpose |
|-------|---------|
| `input.field.tsx` | Text input |
| `number.field.tsx` | Numeric input |
| `textarea.field.tsx` | Multi-line text |
| `password-input.field.tsx` | Password with show/hide |
| `checkbox.field.tsx` | Boolean |
| `select.field.tsx` | Single-value dropdown |
| `enum.field.tsx` | Enum value |
| `dropdown.field.tsx` | Custom dropdown |
| `datetime.field.tsx` | Date/time picker |
| `color.field.tsx` | Color picker |
| `file.field.tsx` | File upload (uses `FileDropzone`) |
| `json.field.tsx` | JSON editor |
| `list.field.tsx` | List of values |
| `peer.field.tsx` | Single relationship |
| `node-kind.field.tsx` | Schema kind selector |
| `relationships/relationship.field.tsx` | Generic relationship dispatcher |
| `relationships/relationship-many.field.tsx` | Many-cardinality relationship |
| `relationships/relationship-hierarchical.field.tsx` | Hierarchical relationship |

**Use `.field.tsx` only inside a `<Form>` from `shared/components/ui/form.tsx`.** Outside a form, use the underlying input from `shared/components/inputs/` or the primitive from `shared/components/ui/`.

### Tab bars

| Need | Use | Location |
|------|-----|----------|
| Tab item (active styling, optional scroll-on-active) | `LinkTab` | `shared/components/ui/link.tsx` |
| Whole tab-bar pattern (parent layout + Outlet + LinkTab) | See [route-architecture.md](../../guidelines/frontend/route-architecture.md) | — |

`LinkTab` derives active state from the URL via `useMatch({ path: href, end: true })`; styling, focus ring, and the optional `scrollIntoViewOnActive` flag live inside the component. Wrap the row of `LinkTab`s in `<nav aria-label="Tabs">` for accessibility and E2E selector stability.

When you wrap `LinkTab` for a feature (e.g. `ProposedChangeTab`), keep the prop name `to` — matching react-router's `NavLink`/`Link`. Don't rename to `href` (that's the rendered DOM attribute, not a prop).

### Detail-page outlet context hooks

Every detail page that has tabs exposes its parent-loaded data via a typed `useOutletContext` wrapper. Children read the wrapper, never `useOutletContext` directly:

| Family | Hook | Location |
|---|---|---|
| Generic objects | `useObjectDetailsOutlet()` | `entities/nodes/object/ui/object-details/use-object-details-outlet.ts` |
| Branches | `useBranchDetailsOutlet()` | `entities/branches/ui/use-branch-details-outlet.ts` |
| Proposed changes | `useProposedChangeOutlet()` | `entities/proposed-changes/ui/use-proposed-change-outlet.ts` |

Each hook throws if used outside its parent route's `<Outlet>`, so misuse fails loudly during dev. The producer side uses `<Outlet context={... satisfies <Context>} />` to keep producer/consumer in lockstep.

### URL helpers

| Family | Helper | Location |
|---|---|---|
| Generic objects (incl. IPAM, resource manager) | `getObjectDetailsUrl(kind, id, overrideParams?, tabSegment?)` | `entities/nodes/utils.ts` |
| Branches | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` | `entities/branches/utils.ts` |
| Proposed changes | `getProposedChangeDetailsUrl(id, tab?, overrideParams?)` | `entities/proposed-changes/utils.ts` |

The `tab` argument on each helper is a string-literal union (e.g. `BranchDetailsTab = "data" | "files" | …`) so callers can't pass an unknown tab.

### Layout

| Need | Use | Location |
|------|-----|----------|
| Horizontal flex layout | `Row` | `shared/components/container/` |
| Vertical flex layout | `Col` | `shared/components/container/` |
| Resizable panels | `ResizablePanelGroup` | `shared/components/ui/resizable.tsx` |
| Scrollable area | `ScrollArea` | `@infrahub/ui` |
| Tooltip | `Tooltip` | `shared/components/ui/tooltip.tsx` |
| Popover | `Popover` | `shared/components/ui/popover.tsx` |
| Accordion | `Accordion` | `shared/components/ui/accordion.tsx` |
| Badge | `Badge` | `shared/components/ui/badge.tsx` |
| Alert | `Alert` | `shared/components/ui/alert.tsx` |
| Pagination | `Pagination` | `shared/components/ui/pagination.tsx` |
| Keyboard shortcut display | `Kbd` | `shared/components/ui/kbd.tsx` |
| Card surface | `Card`, `CardHeader`, `CardContent` | `@infrahub/ui` (see `design-system.md`) |
| Modal/dialog | `Modal`, `ModalOverlay` | `@infrahub/ui` |
| Button | `Button`, `LinkButton` | `@infrahub/ui` |
| Spinner | `Spinner` | `@infrahub/ui` |

### Hooks

| Need | Use | Location |
|------|-----|----------|
| Read route params the route guarantees | `useRequiredParams("foo", "bar")` | `shared/hooks/use-required-params.ts` |
| URL query-param sync | `useFilters` (or `nuqs` directly for typed params) | `shared/hooks/useFilters.ts` |
| Debounced value | `useDebounce` | `shared/hooks/useDebounce.ts` |
| Pagination state | `usePagination` | `shared/hooks/usePagination.ts` |
| Local-storage state | `useLocalStorage` | `shared/hooks/useLocalStorage.ts` |
| Copy to clipboard | `useCopyToClipboard` | `shared/hooks/useCopyToClipboard.ts` |
| Previous value | `usePrevious` | `shared/hooks/usePrevious.ts` |
| Search input state | `useSearch` | `shared/hooks/useSearch.ts` |
| Page title | `useTitle` | `shared/hooks/useTitle.ts` |
| Branch context | `useCurrentBranch` | (entity hook) |
| Date context | `useAtomValue(datetimeAtom)` | `shared/stores/` |

### Domain helpers (cross-entity reuse)

Import another entity's `domain/` types and async functions, or its `ui/` hooks/components. Never import `api/`.

| Source entity | Useful exports |
|---|---|
| `entities/schema` | `useGetSchema`, `SchemaNode` types |
| `entities/branches` | `useGetBranches`, `BranchListItem` |
| `entities/nodes/object` | `useGetObject` from `ui/queries/get-object.query.ts` |
| `entities/nodes/relationships` | `RelationshipComboboxList`, `AddRelationshipAction` |

## Discovery checklist before writing new code

Before adding a new component, run this:

1. `rg -i "<name>" frontend/app/src/shared/components/`
2. `rg -i "<name>" frontend/packages/ui/src/components/`
3. Check the table above for the closest match.
4. If nothing fits, ask: can I extend an existing component, or am I duplicating it with a different name?
5. If you really need something new, justify it in the PR description and update this file.

## Anti-patterns observed in past PRs

| Anti-pattern | Replacement |
|---|---|
| Hand-rolled `gql` string + `graphqlClient.query(...)` for a single node read | `useGetObject({ objectId, objectSchema: { kind: "CoreNode" } })` |
| Reimplementing kind combobox + object combobox + UUID input | Wrap `PeerInput` and add a UUID-mode toggle |
| `<section className="rounded-md border bg-white p-4 shadow-lg">…</section>` | `Card` from `@infrahub/ui` |
| `<div className="flex items-center gap-2">` | `<Row>` from `shared/components/container` |
| Hardcoding system namespace lists on the client | Backend is authoritative; surface via schema if needed |
| Duplicating `useState` between page and selector | Single source of truth — see `dev/guidelines/frontend/page-architecture.md` |
| Hand-rolled tab bar with manual active-state CSS | `LinkTab` + `<nav aria-label="Tabs">` — see `dev/guidelines/frontend/route-architecture.md` |
| `useParams() as { foo: string }` for guaranteed params | `useRequiredParams("foo")` — runtime-checked, no type lie |
