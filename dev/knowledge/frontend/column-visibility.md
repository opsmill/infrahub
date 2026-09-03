# Column Visibility

Location: `frontend/app/src/entities/nodes/columns/`

How show/hide columns works on every schema-driven table: the two URL params, the `ColumnSurface`
that describes one table's rules as data, and which surfaces can reveal a hidden field rather than
only hide a visible one.

## Folder layout

The entity has **no `api/` layer and no `domain/use-cases/`**: it does no I/O — it reads the loaded
schema and two URL params, so everything is `model` + `rules` + `ui`.

```text
entities/nodes/columns/
├── domain/
│   ├── model/
│   │   ├── column-surface.ts               # the ColumnSurface vocabulary — no configs, no identifier
│   │   └── column-visibility-state.ts      # the override map the rules produce and the table consumes
│   └── rules/
│       ├── column-surfaces.ts              # the four concrete surface configs
│       ├── get-column-candidates.ts        # candidate list per surface, each with isDefaultVisible
│       ├── get-column-visibility-state.ts  # the URL trust boundary → TanStack VisibilityState
│       └── toggle-column.ts                # pure rewrites of the two URL name lists
└── ui/
    ├── hooks/
    │   └── use-column-visibility.ts        # the one hook reading both params
    ├── columns-picker.tsx                  # toolbar trigger + count badge
    └── columns-editor.tsx                  # searchable checklist + reset
```

A `ColumnSurface` (`domain/model/column-surface.ts::ColumnSurface`) describes one table's column
rules **as data** — its default-attribute and default-relationship rule functions, its field
exclusions, its ordering, and whether it can reveal. The four concrete configs (`OBJECT_`,
`RELATIONSHIP_`, `IP_ADDRESS_`, `IP_PREFIX_COLUMN_SURFACE`) live one layer out in
`domain/rules/column-surfaces.ts`, because naming a surface means naming the rule functions it
composes and `domain/model` is a pure leaf that may not reach into `domain/rules`. A surface is
resolved from `ObjectTableContext.columnSurface` or named explicitly.

`ColumnSurface` deliberately carries **no identifier**. With nothing to branch on, a consumer cannot
grow an `if (surface === "ipam")` — the refusal is structural, not a convention to remember.
`RELATIONSHIP_COLUMN_SURFACE` is written as `{ ...OBJECT_COLUMN_SURFACE, canReveal: false }`
(`domain/rules/column-surfaces.ts::RELATIONSHIP_COLUMN_SURFACE`) so that its one real difference
from the object surface is the only thing visible. The two IPAM surfaces are spelled out in full
instead: they differ in three of six members, and a spread would bury that.

## Two named params, not one prefixed list

```text
?hide_columns=description,status&show_columns=internal_note
```

`QSP.HIDE_COLUMNS` / `QSP.SHOW_COLUMNS` (`shared/config/qsp.ts::QSP`), each a plain
`parseAsArrayOf(parseAsString)` list (`ui/hooks/use-column-visibility.ts::columnNamesParser`). Both
absent means "the surface's default"; `reset()` removes both
(`ui/hooks/use-column-visibility.ts::useColumnVisibility`).

A single param was tried first and rejected on **encoding**. One param needs a reveal prefix, and
nuqs's `encodeQueryValue` rewrites `+` to `%2B` (it escapes `%`, `+`, space, `#`, `&`, `"`, `'`,
backtick, `<`, `>` and control characters — see `node_modules/nuqs/dist/server.js`), so a `+name`
token would reach the address bar percent-escaped. A JSON object form is worse: every quote becomes
`%22`, exactly as the `filters` param already reads (`parseAsJson`,
`nodes/filters/ui/hooks/use-filters.ts::useFilters`). Two named params need no prefix convention and
stay legible — and a legible, shareable link is the whole point of the feature.

## Delta from the default, never an absolute list

Neither param ever lists every visible column. A name appears only where it **departs** from the
surface's default, so a schema that later gains a column shows that column on an old shared link.
That is a deliberate product decision, not an oversight.

`getColumnVisibilityState` drops any name the current `columnCandidates` does not contain
(`domain/rules/get-column-visibility-state.ts::getColumnVisibilityState`), which is what makes an
old link safe across a schema change, a kind switch, and a relationship tab reading the same params
against a different schema. It also drops a name that agrees with its default, so such a name counts
towards neither the picker's badge nor its reset affordance.

## A kind switch clears the column params

Switching kind clears both params outright (`CLEARED_COLUMN_PARAMS` in
`nodes/object/ui/object-table/object-table-schema-selector.tsx::ObjectTableSchemaSelector`, spread
at both `setObjectTableQueryParams` call sites there, beside the existing `removeFiltersNotInSchema`
prune). Column choices are therefore discarded exactly as filters are.

Carrying them across only *looks* kinder. `useColumnVisibility` writes back the **validated** lists,
so a name the new kind has no column for is silently erased from the URL by the next hide the user
makes under that kind. Clearing up front is the predictable half of that same outcome.

Branch switching is deliberately left alone, matching what filters already do.

## Hidden wins on a contradictory link

With `?hide_columns=x&show_columns=x` there is no param ordering to fall back on, so hiding wins:
a link that says "hide this" must never put a column the sender meant to keep away on screen.

The invariant lives in exactly one place. `getColumnVisibilityState` is the single trust boundary,
and `getRevealedFields` takes the **finished state** rather than the raw params, so it can only read
the answer that boundary already reached — it has no hide list to re-derive the rule from:

```ts
const visibility = getColumnVisibilityState(hiddenNames, shownNames, columnCandidates);
return Object.keys(visibility).filter((name) => visibility[name]).sort();
```

Keep it that way. An earlier revision passed `getRevealedFields` only the shown list, which left it
structurally unable to see a contradiction and forced the hook to re-apply the rule as a second
filter — two enforcement points for one invariant, and a fetch path that would disagree with the
rendered state if either drifted. The `.sort()` is load-bearing for a separate reason: this value
reaches a react-query cache key, so ordering must not change the hash.

## At least one field column always survives

If applying the hide list would leave no field column visible, the trust boundary drops **exactly
one** hide entry — the one for the first column in `columnCandidates` display order that the hide
list names (`domain/rules/get-column-visibility-state.ts::keepOneFieldColumnVisible`). That column
returns to its default, which is necessarily visible, since only a default-visible column ever gets
a `false` entry. Every other hide entry is kept, so as little of the request is discarded as
possible. Display order, not param order, decides the survivor: the same set of names must always
leave the same column standing, however the URL happens to spell it.

It lives in the trust boundary because that is the only place that covers **both** ways zero columns
can be asked for — the picker unchecking the last box, and a hand-written or stale `?hide_columns=`
naming every column at once. In the picker it would leave the crafted URL unguarded; in the table it
would leave the URL and the screen disagreeing. The picker still grays out the last remaining item,
so the clamp is an invariant users never meet, not a second copy of that affordance.

A surface offering nothing but default-hidden columns is returned untouched: there is no hide
request to blame for the empty table, so there is none to relax.

## Reveal is object-list only

| Surface | Hide | Reveal |
|---|---|---|
| Object list | yes | yes |
| IPAM addresses | yes | no (`canReveal: false`) |
| IPAM prefixes | yes | no (`canReveal: false`) |
| Relationship tabs | yes | no (`canReveal: false`) |

`canReveal: false` is implemented as **"candidates == defaults"**
(`domain/rules/get-column-candidates.ts::getColumnCandidates`), so the picker offers nothing to
reveal and `show_columns` names are dropped by the trust boundary. There is no `if (isIpam)`
anywhere.

Reveal needs three legs, and only the object list has all three:

1. **A ColumnDef must exist** — `getObjectFieldsColumns` filters the field list through the list-view
   rules *before* any ColumnDef exists, so it takes an optional `fields` argument
   (`nodes/object/ui/object-table/utils/get-object-table-columns.tsx::getObjectFieldsColumns`); when
   omitted, behavior is unchanged.
2. **The field must be in the GraphQL selection set** — `getObjects` threads `revealedFields` into its
   injectable `getAttributesVisible` / `getRelationshipsVisible` overrides
   (`nodes/object/domain/use-cases/get-objects.ts::getObjects`), which take an optional
   `revealedNames?: ReadonlySet<string>` that opens the `display === "extra"` gate and **only** that
   gate — the attribute-kind whitelist and the relationship-kind switch still apply
   (`nodes/object/domain/rules/get-attributes-visible-in-list-view.ts::getAttributesVisibleInListView`,
   `nodes/object/domain/rules/get-relationships-visible-in-list-view.ts::getRelationshipsVisibleInListView`).
3. **The react-query cache key must change** — see below.

`get-object-relationships-from-api.ts` has no equivalent injectable seam, which is why relationship
tabs are hide-only.

## Where to actually see reveal working

Reveal looks broken until you know where to point it, because **nothing in the demo dataset is
hidden by default**. Every attribute on `InfraDevice` and friends is `display: "default"`, so the
Columns popover there lists only already-visible fields and `show_columns` never appears. That is
correct behavior, not a bug — and it is the first thing to check before concluding the feature is
half-wired.

`show_columns` only has meaning where a *schema author* marked a field `display: "extra"`. Across
the 128 kinds in the demo schema there are eleven, on three kinds:

| Kind | `extra` fields | Demo objects |
|---|---|---|
| `CoreAccountGroup` | `origin` | 6 — **use this one** |
| `CoreFileObject` | `file_type`, `file_name`, `checksum`, `storage_id`, `file_size` | 0 |
| `InfraCircuitContract` | the same five, inherited | 0 |

So the working manual check is `/objects/CoreAccountGroup`: the popover offers **Origin** unchecked,
ticking it writes `?show_columns=origin`, and the request gains `origin { id value __typename }`.
Note the cells then render `-` because `origin` is null on all six groups — an empty cell is the
correct outcome and does *not* mean the fetch leg failed. Confirm against the request body, not the
rendered value.

Query the live schema for candidates rather than grepping `models/`, which sets `display` nowhere:

```bash
curl -s "http://localhost:8000/api/schema?branch=main" -H "X-INFRAHUB-KEY: $KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(
      f\"{n['kind']}.{a['name']}\" for n in d['nodes']+d['generics']
      for a in n.get('attributes',[]) if a.get('display')=='extra'))"
```

## The IPAM `display: "extra"` divergence

IPAM's **attribute** filters exclude only a hardcoded name list — they check neither `display` nor
`kind`
(`ipam/ip-addresses/domain/rules/get-ip-address-attributes-visible-in-list-view.ts::IP_ADDRESS_ATTRIBUTES_EXCLUDED_IN_LIST`,
`ipam/ip-prefixes/domain/rules/get-prefix-attributes-visible-in-list-view.ts::PREFIX_ATTRIBUTES_EXCLUDED_IN_LIST`)
— so `extra` attributes are **already visible** on IPAM tables.

IPAM's **relationship** paths do delegate to `getRelationshipsVisibleInListView`
(`ipam/ip-addresses/domain/rules/get-ip-address-relationships-visible-in-list-view.ts::getIpAddressRelationshipsVisibleInListView`,
and `IP_PREFIX_COLUMN_SURFACE` uses it directly), which **does** drop `extra`.

So "reveal would be a no-op on IPAM" is true for attributes and false for relationships. Both halves
matter: do not "fix" one of them alone.

## `_resource_from_pool` polarity

`getRelationshipsVisibleInListView` deliberately **includes** resource-pool relationships so their
data is fetched — "to get data from `_resource_from_pool` relationships but will be hidden in UI"
(`nodes/object/domain/rules/get-relationships-visible-in-list-view.ts::getRelationshipsVisibleInListView`).
Only the *object* builder strips their columns
(`get-object-table-columns.tsx::getDefaultFieldsColumnSchemas`); neither IPAM builder does, so IPAM
tables genuinely render them.

Hence `excludeField: isFromResourcePoolRelationship` is set on the object surface
(`domain/rules/column-surfaces.ts::OBJECT_COLUMN_SURFACE`) and inherited by the relationship surface
through its spread, while the two IPAM surfaces use `excludeField: () => false`
(`column-surfaces.ts::IP_ADDRESS_COLUMN_SURFACE` and `::IP_PREFIX_COLUMN_SURFACE`). Excluding them
on the IPAM surfaces would hide real columns from the picker — the intuitive reading is backwards.

## `objectQueryKeys.list` folds revealed field names

A revealed field widens the GraphQL selection set, so it must be part of the query key or a reveal
reads a page cached without that field — a column of empty cells that fills in on some later
unrelated refetch. `objectQueryKeys.list` folds `revealedFields` in through a **conditional spread**
(`nodes/object/ui/queries/object.query-keys.ts::objectQueryKeys`), so the key stays byte-identical
for callers that never reveal anything and no cache is invalidated on deploy. `getRevealedFields`
sorts its output (`domain/rules/get-column-visibility-state.ts::getRevealedFields`) so the key does
not depend on click order.

`objectQueryKeys.count` needs no equivalent: the count query selects no fields.

`objectQueryKeys.detail` already folded field names in — `list` was the outlier, a
pre-existing gap this feature had to fix rather than a gap it introduced.

## The column controls are opt-in, per table

`ObjectTableProvider` takes `supportsColumnVisibility?: boolean`, defaulting to **false**
(`nodes/object/ui/object-table/object-table-context.tsx::ObjectTableContextProps` and
`::ObjectTableProvider`). It is the table's declaration that it actually honors the two params —
that it renders a `DataTable` with a `columnVisibility` state.

Both controls ask before offering anything: the toolbar gates `<ColumnsPicker>` on it
(`nodes/object/ui/objects-manager-toolbar.tsx::ObjectsManagerToolbar`), and the column header's hide
entry returns `null` without it (`object-table/cells/table-column-header.tsx::HideColumnMenuItem`).
The reader `useSupportsColumnVisibility()` (`object-table-context.tsx::useSupportsColumnVisibility`)
is non-throwing and falls back to `false`, because a header cell may render outside any provider —
and no provider means no table claimed the capability, which is the same answer.

`HideColumnMenuItem` also owns its own leading `<MenuSeparator />`
(`object-table/cells/table-column-header.tsx::HideColumnMenuItem`)
rather than being wrapped in one, so gating it off cannot leave a dangling rule at the bottom of the
menu.

`ObjectsManagerToolbar` is rendered in 8 places, and only 3 managers opt in:
`objects-manager.tsx::ObjectsManager`, `ip-address-manager.tsx::IpAddressManager` and
`ip-prefix-manager.tsx::IpPrefixManager`. There is no `showColumnsPicker` prop and no
`ObjectsManagerToolbarProps` interface any more — an earlier revision had both, and they were the
wrong shape.

### Why one capability, not a gate per surface

The same defect surfaced **three** separate times: an inert control on a table that renders the
shared toolbar or the shared column header without consuming `columnVisibility`. The two
role-management pages were the first (their tables are `RoleTable` and friends). Proposed Changes
was the third, and it arrived by a different route —
`proposed-changes-manager.tsx::ProposedChangesManager` provides an `ObjectTableProvider`, and
`proposed-changes-table.tsx::ProposedChangesTable` renders a `ListBox`, never a `DataTable`, while
passing `schema` to five headers purely so they can sort.

That last one is why gating on the presence of `schema` was the wrong fix: on this codebase `schema`
on a header means *"this header can sort"*, not *"this table supports column visibility"*. One
boolean the table declares makes the whole class of defect impossible, instead of fixing instances
as they are found.

Relationship tabs get their own toolbar row instead
(`relationships/ui/relationship-table/relationship-table-toolbar.tsx::RelationshipTableToolbar`),
which takes `schema` as a prop and names `RELATIONSHIP_COLUMN_SURFACE` explicitly, because two of
`RelationshipTable`'s three hosts render it without an `ObjectTableProvider`.

### Relationship headers depend on `isDisabled` to stay off the object surface

`useColumnSurface()` (`nodes/object/ui/object-table/object-table-context.tsx::useColumnSurface`) is
non-throwing and falls back to `OBJECT_COLUMN_SURFACE`, and two of `RelationshipTable`'s three hosts
render it with no `ObjectTableProvider` above them at all. Relationship headers avoid that fallback
today only by accident of a different decision: `RelationshipTable` passes `headerProps:
{ isDisabled: true }` into `getObjectTableColumns`
(`relationships/ui/relationship-table/relationship-table.tsx::RelationshipTable`), and
`TableColumnHeader` (`object-table/cells/table-column-header.tsx::TableColumnHeader`) short-circuits
on that flag to `TableColumnHeaderSimple`, so no menu — and therefore no surface lookup — is ever
mounted.

Dropping `isDisabled` to enable header sorting on relationship tabs would silently resolve the
object surface, whose `canReveal: true` would offer `display: "extra"` fields for reveal. The
relationship fetch path never requests those fields: it has no injectable rule seam equivalent to
the `getAttributesVisible` / `getRelationshipsVisible` overrides on
`nodes/object/domain/use-cases/get-objects.ts::getObjects` (see [Reveal is object-list
only](#reveal-is-object-list-only)). The picker would happily list the field, the URL would gain a
`show_columns` entry, and the column would render permanently empty — the fetch leg simply is not
there. So thread the surface in explicitly, the way `RelationshipTableToolbar` already does,
*before* removing that flag.

## Three column ids the picker never offers

`id`, `objectKind` and `actions` are synthesized outside the schema-derived middle section of the
table (`get-object-table-columns.tsx::getObjectIdentifierColumns` and `::getObjectGenericColumns`;
`get-object-actions-column.tsx::getObjectActionsColumn`;
`relationships/ui/relationship-table/get-relationship-actions-column.tsx::getRelationshipActionsColumn`),
so they are not schema fields at all. They are listed as `fixedColumnIds` on every surface and
filtered out of the candidate list (`domain/rules/get-column-candidates.ts::getColumnCandidates`),
so they never reach the picker.

Those three ids are also why the grid template is `repeat(columnCount - 2, auto) 1fr 2.5rem`: the
last two tracks are the identity and actions columns. Hiding every field column leaves two headers,
and `repeat(0, auto)` is invalid CSS — the CSSOM would reject the whole declaration and collapse the
grid to one implicit column, doubling the height of every row. `defaultGridTemplateColumns`
(`shared/components/table/data-table.tsx`) therefore drops the `repeat()` entirely at two columns or
fewer.

## Known limitations

- **Any change to the revealed set restarts an infinite list.** It changes the react-query key (see
  [`objectQueryKeys.list` folds revealed field names](#objectquerykeyslist-folds-revealed-field-names)),
  so an infinite-scroll list starts over at page 1: the accumulated pages and the scroll position are
  lost. This is inherent to keying on the revealed field names; the alternative is refetching every
  accumulated page under the new selection set.

  **Hiding is free only for a column that was visible by default.** Hiding *a revealed* column pays
  the same cost — which is the one case the feature exists for: `hideColumn` drops the field from
  `shown` rather than adding it to `hidden` (`domain/rules/toggle-column.ts::hideColumn`, and the
  comment above it says so), `revealedFields` shrinks by one, the conditional spread in
  `objectQueryKeys.list` loses its element, and the list restarts. Only a `hide_columns` write is
  free — that param never reaches the key.

## Known follow-ups (to be filed)

1. **Column reordering** — promised in the ticket, not in this change.
2. **Unify the three column builders** onto a shared field-column helper — gated on adding IPAM
   component tests first; both IPAM builders key special cells on attribute *name*, with no coverage.
3. **Align IPAM attribute filtering** to `getAttributesVisibleInListView`. This is a behavior change
   that removes currently-visible columns, so it needs product sign-off.
4. **Durable per-user column preferences** via the backend `preferences` entity, instead of URL-only
   state.
5. **Wire the 5 role-management tables** to `columnVisibility`, then drop the `showColumnsPicker`
   opt-in.
6. **Add reveal to relationship tabs** — needs an injectable rule seam in
   `get-object-relationships-from-api.ts`, field names folded into `relationshipsQueryKeys.list`, and
   relationship-table component tests.
7. **Build a semantic-token layer for Tailwind.** `dev/guidelines/frontend/styling.md` tells you to
   prefer semantic theme tokens over raw palette classes, but no such tokens exist: there are no
   `foreground`-style classes anywhere in `frontend/`, `tailwind.config.js` extends only
   `custom-blue*`, and neither `app/src/app/styles/index.css` nor `packages/ui/src/index.css`
   defines a `@theme` palette. `text-stone-400` and friends are the de-facto house pattern. Until the
   token layer lands, that guideline cannot be followed — applying it would silently drop styling.
8. **`ip_prefix` is prepended without being filtered out of the spread**
   (`ipam/ip-addresses/domain/rules/get-ip-address-relationships-visible-in-list-view.ts::getIpAddressRelationshipsVisibleInListView`).
   It does **not** duplicate today:
   the prepend is followed by a spread of `getRelationshipsVisibleInListView(relationships)`, which
   drops `ip_prefix` because its `RelationshipKind` defaults to `Generic`. So the shape is safe only
   by accident — a schema that gave that relationship an accepted kind (`Attribute`, `Parent`, or
   `Hierarchy` with cardinality one) would emit it twice. The picker's candidate list is deduped
   defensively against exactly that (`domain/rules/get-column-candidates.ts::getColumnCandidates`), but
   the IPAM address builder has no
   such guard and would render two columns with the id `ip_prefix`. Filter the prefix relationship
   out of the spread instead of relying on its kind.

## See also

- [Frontend Entities Structure](entities-structure.md) — the layering this entity follows, and the
  `display: "extra"` tier the reveal path opens up.
