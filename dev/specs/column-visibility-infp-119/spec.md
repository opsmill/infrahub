# Feature Specification: User-controlled column visibility in list views

**Feature Branch**: `ple-column-visibility-ifc-3079`
**Created**: 2026-08-30
**Status**: Implemented
**Input**: User description: "Show / hide columns in list view"
**Source ticket**: [INFP-119](https://opsmill.atlassian.net/browse/INFP-119)
**Epic**: [IFC-3079](https://opsmill.atlassian.net/browse/IFC-3079)

> Written retrospectively, after the implementation merged into review. The decisions below were
> made and approved in sequence during the build; this file records them where they can be found
> again, rather than claiming they were written first.

## Clarifications

### Session 2026-08-30 (with product, recorded on the ticket)

- Q: Is per-user stickiness a hard requirement, or is a shareable-but-not-sticky URL acceptable for
  v1? → A: URL is acceptable. Durable per-user preferences are a fast-follow through the backend
  `preferences` entity and cross the API governance gate.
- Q: How should `display: "extra"` attributes behave? → A: The same as any other attribute —
  revealable, with no special tier in the picker.
- Q: One entry point or two? → A: Two — a global control in the table plus a "Hide" option in the
  column header menu.
- Q: Should a schema that later gains a column show it on an existing shared link? → A: Yes. The
  params record only departures from the schema default.
- Q: Is column reordering in scope? → A: No — file a separate card.

### Session 2026-08-30 (build-time decisions)

- Q: IPAM's attribute filters never check `display`, so `extra` attributes are already visible
  there. Align IPAM to the object rule, or leave it? → A: Leave it. Aligning removes columns users
  can see today, in builders with no component tests. Note the divergence is only half true, and
  the halves must not be fixed separately: IPAM's *attribute* filters ignore `display` entirely, but
  its *relationship* paths do delegate to the shared rule, which does drop `extra`. So "reveal would
  be a no-op on IPAM" holds for attributes and not for relationships.
- Q: Relationship tables render no toolbar and their headers are read-only. How do they get the
  feature? → A: A minimal Columns-only toolbar row; no header menu.
- Q: Hiding a column with an active sort or filter? → A: Never discard either. Mark such fields in
  the picker and keep them selectable.
- Q: One prefixed URL param or two named ones? → A: Two named params. A reveal prefix cannot survive
  the query-string encoder legibly, and a legible shared link is the point of the feature.
- Q: What does a contradictory link mean? → A: Hiding wins. With two params there is no ordering to
  fall back on.
- Q: What if the user hides every column? → A: Refuse. Keep one field column visible, enforced where
  URL input is validated so a hand-written link cannot bypass it.
- Q: Should switching object kind keep the column params? → A: No — clear them, matching what the
  kind switcher already does for filters. Re-selecting the kind already in view is not a switch and
  clears nothing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trim a wide table to the task at hand (Priority: P1)

An engineer opens a device list whose schema defines a dozen columns. Only four matter for the job
in front of them. They open the **Columns** control in the toolbar, uncheck the rest, and the table
redraws immediately. Reloading keeps their choice.

**Acceptance scenarios**:

1. Given a list view with columns beyond the ones needed, when the user unchecks a column in the
   Columns control, then that column's header and every one of its cells disappear and the URL
   records the departure.
2. Given a link carrying hidden columns, when a colleague opens it, then they see the same reduced
   table.
3. Given hidden columns, when the user selects reset, then the schema's own layout returns and the
   params leave the URL entirely.
4. Given every field column unchecked, when the user tries to uncheck the last one, then the control
   refuses and says why — a table with no data columns is not a state the product offers.

### User Story 2 - Reveal an attribute the schema hides (Priority: P2)

A schema author marked several attributes `display: "extra"`, which keeps them out of list views
altogether. An operator auditing those values needs them on screen without a schema change that
would affect every user.

**Acceptance scenarios**:

1. Given a kind with an `extra` attribute, when the user opens the Columns control on the object
   list, then that attribute is offered, unchecked.
2. Given the user checks it, then a column appears **with values in it** — the field enters the data
   request, not merely the layout.
3. Given a revealed column, when the user unchecks it, then the URL returns to carrying no reveal.

### User Story 3 - Hide a column without leaving the table (Priority: P2)

A user scanning a table wants one noisy column gone and does not want to open a settings popover to
do it.

**Acceptance scenarios**:

1. Given any sortable column header, when the user opens its menu, then a **Hide column** action
   appears after the existing filter entry.
2. Given the user chooses it, then the column disappears and the URL records it exactly as the
   toolbar control would.
3. Given a table that does not honour column visibility, then the action does not appear at all.

### User Story 4 - Keep a sort or filter that is no longer on screen (Priority: P3)

A user sorts by a column, then hides it.

**Acceptance scenarios**:

1. Given an active sort on a column, when that column is hidden, then the sort stays applied and
   stays visible in the toolbar.
2. Given an active filter on a hidden column, then the filter tag stays present and removable.
3. Given a field carrying either, then the Columns control marks it and still allows the toggle.

### Edge Cases

- A link naming a field the current schema does not have: dropped, silently and per-name. This is
  what lets an old link survive a schema change, a kind switch, and a relationship tab reading the
  same params against a different schema.
- A link naming the same field in both params: hiding wins.
- A link hiding every field column: one is handed back — the first in display order, so the same set
  of names always leaves the same column standing.
- A field named `constructor` or `toString`: read with own-property semantics, not `in`, so a
  prototype member cannot masquerade as a visibility entry.
- Malformed params (`?hide_columns=`, `,,`, repeated keys): all reduce to nothing through the same
  validation.
- The row's identifying column, the kind column, and the actions column are never offered and can
  never be hidden through any input.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users can hide any schema-derived column on the object list, relationship tabs, the
  IPAM address list, and the IPAM prefix list.
- **FR-002**: Users can reveal a `display: "extra"` attribute on the object list. The other three
  surfaces are hide-only; their fetch paths expose no seam through which a revealed field could be
  requested.
- **FR-003**: Column choice persists in the URL and is shareable. Reload preserves it.
- **FR-004**: The params record only departures from the schema default, so a schema that gains a
  column later shows it on an existing link.
- **FR-005**: Both params absent means the schema's own layout. Clearing removes them rather than
  writing the current default back.
- **FR-006**: A reset affordance is reachable whenever either param is present — including when
  validation has dropped every name it carried, which would otherwise leave an uncleanable param.
- **FR-007**: The number of departures is shown on the control, counting reveals as well as hides.
- **FR-008**: The row's identity, kind, and actions columns are never hidable.
- **FR-009**: A hide request never empties the table. If applying it would leave no field column
  visible, one hide entry is dropped — the first in display order — so a column returns to its
  default. A surface whose every candidate is hidden *by default* is out of scope for this rule:
  there is no hide entry to give back, and nothing has been hidden.
- **FR-010**: Hiding a column never discards its sort or filter, and the picker marks fields
  carrying either.
- **FR-011**: Two entry points write identical state: a toolbar control and a header-menu action.
- **FR-012**: Both entry points appear only on tables that honour the params.
- **FR-013**: Switching object kind clears the params, matching the existing behavior for filters.
- **FR-014**: Untrusted URL input is validated in exactly one place.

### Key Entities

- **Column surface** — one table's column rules expressed as data: which rule functions produce its
  defaults, which fields it excludes, how it orders them, and whether it can reveal. Carries no
  identifier, so no consumer can branch on which surface it has.
- **Column candidate** — a field the picker may offer, with whether the surface shows it by default.
- **Column visibility state** — the override map the table consumes, holding only departures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user reduces a twelve-column list to four in four interactions and one reload
  preserves it.
- **SC-002**: A pasted link reproduces the sender's column set on a different session.
- **SC-003**: A `display: "extra"` attribute reaches the screen with values, without a schema change.
- **SC-004**: No hide request — from the control or a hand-written URL — produces a table with zero
  field columns, and no input hides the identity column.
- **SC-005**: A link written against an older schema still renders, dropping only names that no
  longer exist.
- **SC-006**: No user's cached data is invalidated by the deploy: a request that reveals nothing
  hashes to the key it hashed to before.

## Assumptions

- Frontend-only. No schema, GraphQL, REST, dependency, CI, or auth change.
- The `display: "extra"` tier already exists and is authored in schemas; this feature makes it
  reachable rather than introducing it.
- Column ordering is out of scope and unchanged, including the pre-existing difference between how
  the object list and the IPAM lists order their columns.
- Durable per-user preferences are out of scope and would cross the API governance gate.
