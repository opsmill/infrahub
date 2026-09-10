# Column Visibility

Location: `frontend/app/src/entities/nodes/columns/`

How a user chooses which columns a schema-driven list view shows, why that choice lives in the URL,
and why only one of the four tables can bring a hidden field back.

## The choice lives in two URL params

```text
?hide_columns=description,status&show_columns=internal_note
```

Both are plain comma-separated field-name lists, so the link stays legible and shareable — the whole
point of the feature, and the reason a single param carrying a reveal prefix was rejected: a prefix
does not survive the query-string encoder legibly.

Each param records a **delta from the surface's default layout, never a snapshot** of what is
visible. A name appears only where it departs from the default, so both params absent means "the
schema's own layout", and a schema that later gains a column shows it on an old shared link.
Clearing the choice removes the params rather than filling them in.

That one decision explains most of the rest:

- **Unknown names are dropped.** A name the current schema has no column for is discarded, which is
  what makes an old link safe across a schema change, a kind switch, and a relationship tab reading
  the same params against a different schema. A name that agrees with its default is dropped too, so
  it counts towards neither the picker's badge nor its reset affordance.
- **Hiding wins on a contradictory link.** With `?hide_columns=x&show_columns=x` there is no param
  ordering to fall back on, so a link that says "hide this" never puts that column on screen.
- **A link that hides every field column gets one back** — the first in display order, so the same
  set of names always leaves the same column standing, however the URL happens to spell it.
- **Switching to a different kind clears both params**, exactly as it already clears filters.
  Re-selecting the kind already in view clears nothing.

## The four surfaces

| Surface | Hide | Reveal |
|---|---|---|
| Object list | yes | yes |
| IPAM addresses | yes | no |
| IPAM prefixes | yes | no |
| Relationship tabs | yes | no |

Hiding is cheap: the table library is told to hide a column it already has. Revealing is not — the
field has to reach both the GraphQL selection set and the react-query cache key, or the column
renders permanently empty, or fills in on some later unrelated refetch. Only the object list's fetch
exposes a seam for injecting extra field names, so the other three surfaces are hide-only by design,
not half-finished.

Hide-only is data, not a branch: those surfaces offer the picker no candidates beyond their own
defaults, so there is no `if (isIpam)` anywhere. Per-surface differences live on a `ColumnSurface`
config that deliberately carries no identifier — with nothing to branch on, a consumer cannot grow
a branch.

## The controls are opt-in, per table

A table must declare that it honors the two params before either control appears. The toolbar picker
and the column header's hide action both ask first, and the default is off.

Keep it that way. The same defect appeared **three** times during the build: a control offered on a
table that renders the shared toolbar or the shared column header without ever consuming a
column-visibility state, so ticking a box did nothing. Two role-management tables were the first;
the third was a table that provides the surrounding context but renders a list box instead of a data
table, passing a schema to its headers purely so they can sort. That last one is why gating on "does
this header have a schema?" was the wrong fix — on this codebase a schema on a header means *this
header can sort*. One boolean the table declares makes the whole class of defect impossible,
instead of fixing instances as they are found.

## Where to actually see reveal working

Reveal looks broken until you know where to point it, because **nothing in the demo dataset is
hidden by default**. `show_columns` only means something where a schema author marked a field
`display: "extra"`, and the `models/` directory sets `display` nowhere. Across the demo schema there
are eleven such fields on three kinds, and only one of those kinds has objects behind it:
`CoreAccountGroup.origin`.

So the working manual check is `/objects/CoreAccountGroup`. The picker offers **Origin** unchecked,
ticking it writes `?show_columns=origin`, and the request gains `origin`. The cells then render `-`
because `origin` is null on all six groups — an empty cell is the correct outcome here, so confirm
against the request body, not the rendered value.

To find candidates on any other deployment, query the live schema rather than grepping `models/`:

```bash
curl -s "http://localhost:8000/api/schema?branch=main" -H "X-INFRAHUB-KEY: $KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(
      f\"{n['kind']}.{a['name']}\" for n in d['nodes']+d['generics']
      for a in n.get('attributes',[]) if a.get('display')=='extra'))"
```

## Known limitations

- **Any change to the revealed set restarts an infinite list.** The revealed names are part of the
  react-query key, so the list starts over at page 1, losing its accumulated pages and scroll
  position. Inherent to keying on them; the alternative is refetching every accumulated page under
  the new selection set.
- **Hiding is free only for a column that was visible by default.** Hiding a *revealed* column drops
  it from `show_columns`, which shrinks the revealed set and so restarts the list the same way. Only
  a `hide_columns` write never reaches the cache key.

## Known follow-ups

The tracked list is in `dev/specs/column-visibility-infp-119/tasks.md`, including a latent
`ip_prefix` duplication in the IPAM address relationship rule that is safe only by accident of that
relationship's kind. The ones that shape how the feature behaves today:

1. Column reordering.
2. Unify the three column builders onto a shared field-column helper — gated on the IPAM tables
   gaining component tests, since both IPAM builders key special cells on attribute *name* with no
   coverage.
3. Align IPAM attribute filtering to the object rule. This removes columns users can see today, so
   it needs product sign-off.
4. Durable per-user column preferences through the backend `preferences` entity, instead of URL-only
   state.
5. Wire the role-management tables to a column-visibility state, then drop their opt-out.
6. Add reveal to relationship tabs — needs a rule seam in the relationships fetch, the field names
   folded into the relationships list key, and relationship-table component tests.

## Where the code lives

The entity does no I/O — it reads the loaded schema and the two URL params — so it has no `api/` and
no `domain/use-cases/`: just `domain/model` (the vocabulary), `domain/rules` (the four surface
configs and the pure rules) and `ui` (one hook, the picker, the editor).

Two symbols orient the rest. `ui/hooks/use-column-visibility.ts::useColumnVisibility` is the only
reader of the two params, and `domain/rules/get-column-visibility-state.ts::getColumnVisibilityState`
is the single trust boundary, where untrusted values become a validated state — every rule stated
above is enforced there and nowhere else. The reveal path threads outward from the hook into the
object list's fetch and its list query key, under `entities/nodes/object/`.

## See also

- [Frontend Entities Structure](entities-structure.md) — the layering this entity follows, and the
  `display: "extra"` tier the reveal path opens up.
