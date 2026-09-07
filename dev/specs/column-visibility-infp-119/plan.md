# Implementation Plan: User-controlled column visibility in list views

**Branch**: `ple-column-visibility-ifc-3079` | **Spec**: `spec.md` | **Status**: Implemented

## Summary

Add a `columns` entity holding the pure rules for column visibility, thread one `columnVisibility`
prop into the shared table component, and give the object list the three legs a reveal needs. Two
entry points — a toolbar checklist and a header-menu action — write two named URL params. The other
three surfaces are hide-only.

The load-bearing choice is that visibility is enforced by the table library rather than by rebuilding
column definitions, so three of the four surfaces need no change to how they construct columns. The
IPAM builders in particular are untouched: they key special cells on attribute *name* and have no
component tests, so altering what they emit would silently change cell rendering.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19 (React Compiler enabled — manual memoization is
forbidden)
**Primary Dependencies**: `@tanstack/react-table` 8.21.3 for `state.columnVisibility`; `nuqs` for
URL state; `@infrahub/ui` for the popover, menu, and badge primitives
**Testing**: Vitest browser mode for unit and component tests; pytest-playwright for E2E
**Target Platform**: Web frontend (`frontend/app`)
**Project Type**: Frontend-only
**Performance Goals**: No additional network requests on the hide path; a reveal adds exactly the
revealed fields to an existing query
**Constraints**: A shared link must stay legible; no user's cache may be invalidated by the deploy

## Constitution Check

### III. Type Safety & Explicit Contracts

The domain layer declares its own `ColumnVisibilityState` rather than importing the table library's
alias, so `domain/` holds no framework type. The two vocabularies meet at one annotated line in the
hook. `FieldSchema` is exported once from the schema model instead of re-declared per consumer.

### IV. Test Discipline

Every pure rule has colocated unit tests written before its implementation. The shared table seam
gained a component test with no mocks. The two defects review found each gained a regression test
that was confirmed failing first. One E2E covers the round-trip through the real router.

Gaps, declared rather than glossed: reveal has no E2E, and the IPAM tables have no component tests.
Both are recorded as follow-ups; the second is a prerequisite for the builder-unification card.

### VI. Security & Input Boundaries

Two URL params are untrusted input. They are validated in exactly one function, which drops any name
the current schema does not carry, refuses to hide the row's identity, and clamps to at least one
visible column. Revealed names only un-filter fields already present on the schema, so no crafted
value can reach the query as a new field. Own-property reads, not `in`, so a prototype member cannot
be mistaken for a visibility entry.

### VII. Simplicity & Maintainability

Per-surface differences are data on a frozen config object, not branches: no consumer can write
`if (surface === "ipam")` because the surface carries no identifier. Three shared-primitive
extractions were considered and rejected on measurement — the shared part was smaller than the
wrapper each site needed.

## Project Structure

### Documentation (this feature)

```text
dev/specs/column-visibility-infp-119/
├── spec.md      # what and why, with the decisions as they were taken
├── plan.md      # this file
└── tasks.md     # the ordered build, as executed
```

Durable knowledge went to `dev/knowledge/frontend/column-visibility.md`, which is the page a future
reader should find first. Two test-environment gotchas went to
`dev/guides/frontend/writing-component-tests.md`.

### Source code touch list

```text
frontend/app/src/entities/nodes/columns/          # NEW entity — no api/, no domain/use-cases/
├── domain/model/column-surface.ts                # the ColumnSurface vocabulary
├── domain/model/column-visibility-state.ts       # the override map
├── domain/rules/column-surfaces.ts               # the four concrete surfaces
├── domain/rules/get-column-candidates.ts         # schema + surface -> what the picker may offer
├── domain/rules/get-column-visibility-state.ts   # the single trust boundary
├── domain/rules/toggle-column.ts                 # pure rewrites of the two name lists
├── ui/hooks/use-column-visibility.ts             # the one hook reading both params
├── ui/columns-picker.tsx                         # toolbar trigger + count badge
└── ui/columns-editor.tsx                         # searchable checklist + reset

frontend/app/src/shared/
├── components/table/data-table.tsx               # + columnVisibility, + empty-grid guard
└── config/qsp.ts                                 # + the two param keys

frontend/app/src/entities/schema/domain/model/schema.ts        # + the shared FieldSchema union

frontend/app/src/entities/nodes/object/
├── domain/rules/get-attributes-visible-in-list-view.ts        # + optional reveal opt-in
├── domain/rules/get-relationships-visible-in-list-view.ts     # + optional reveal opt-in
├── domain/use-cases/get-objects.ts                            # + revealedFields into the request
├── ui/queries/object.query-keys.ts                            # + revealedFields into the list key
├── ui/object-table/utils/get-object-table-columns.tsx         # + an options object with fields
├── ui/object-table/object-table.tsx                           # all three reveal legs + the map
├── ui/object-table/object-table-context.tsx                   # + surface and capability
├── ui/object-table/object-table-schema-selector.tsx           # clear the params on a kind change
├── ui/object-table/cells/table-column-header.tsx              # + the hide action
├── ui/objects-manager-toolbar.tsx                             # + the picker, behind the capability
└── ui/objects-manager.tsx                                     # opts in

frontend/app/src/entities/ipam/{ip-addresses,ip-prefixes}/ui/  # pass the prop; opt in; builders untouched
frontend/app/src/entities/nodes/relationships/ui/relationship-table/
├── relationship-table.tsx                        # pass the prop, host the toolbar row
└── relationship-table-toolbar.tsx                # NEW — one control, schema as a prop

tests/e2e/objects/test_object_columns.py          # NEW — the link round-trip
```

Also changed, outside the feature proper: `frontend/app/AGENTS.md` (registers the knowledge page),
`dev/knowledge/frontend/entities-structure.md` (registers the entity), and
`frontend/app/.betterer.results` (re-anchors one pre-existing error whose line an edit shifted).

## The three legs a reveal needs

Reveal needs three legs and only the object list has all three, which is why the other surfaces are
hide-only rather than merely unfinished:

1. A column definition must exist. The builder filters the field list through the list-view rules
   *before* any definition is created, so it takes an optional resolved field list; omitted, its
   behavior is unchanged.
2. The field must be in the request. The object fetch already exposed injectable rule overrides;
   revealed names travel through those, opening only the `display: "extra"` gate and leaving the
   attribute-kind and relationship-kind gates intact.
3. The cache key must change. Revealed names join the list key through a conditional spread, so a
   caller that reveals nothing hashes exactly as before and no cache is invalidated on deploy.

The relationships fetch has no equivalent seam. Adding one is a filed follow-up, gated on the
relationship table first gaining component tests.

## Complexity Tracking

| Decision | Simpler alternative | Why the simpler one was rejected |
|---|---|---|
| Two named params | One param with a `+`/`-` prefix | The query-string encoder rewrites `+`, so every reveal link would read `%2B…`. A JSON object is worse — every quote becomes `%22`. Measured against the encoder, not assumed. |
| Enforce the one-column minimum in the trust boundary | Guard it in the picker | The picker is not the only writer; a hand-written link has to hit the same rule. |
| `ColumnSurface` as function-valued data | A surface-id enum with branches | Three surfaces have genuinely different default rules. Removing the identifier makes "no consumer branches on the surface" structural rather than a convention to remember. |
| One capability flag on the table context | A gate at each entry point | The same defect — a control on a table that cannot honour it — appeared on three separate surfaces. Gating twice fixed instances; one capability makes the class impossible. |
| Leave the IPAM builders alone | Unify all three column builders | The IPAM builders key special cells on attribute name and have no component tests. Unifying is filed, with those tests as its prerequisite. |
| Keep the empty-grid guard in the table | Remove it now the clamp exists | The clamp makes it unreachable from the picker, but the table serves surfaces that build their own column sets. |
