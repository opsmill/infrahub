# Review of collapsible-sections rev 6

Review level: full (`emil-ui-polish`, `emil-surfaces`, `break-ui`, `emil-ui-review`,
`emil-prep-for-prod`), run on 2026-11-19 on the running prototype at 1440 × 900 and
1024 × 768, in light and dark mode, with demo data and with the worst-case data set.

The fixes are in rev 7 (`directions/collapsible-sections-rev-07.tsx`). Rev 6 is unchanged.
Line numbers below are in `directions/collapsible-sections-rev-06.tsx` unless a file is
named.

Every finding is fixed or accepted with a reason, so the gate is clean.

## Worst-case data set

A "Demo data / Worst case" switch at the bottom centre of the prototype (`index.tsx`)
reloads the page with `dj.data=worst`. The records in `context.tsx` then change as follows:
- the staged change is named
  `infracircuitterminationendpointinterfaceassignment_maintenance_window_contact_email_add_and_24_more`
  (102 characters), from the longest kind in the mock data and a 32-character attribute
  name, the longest the schema accepts (`DEFAULT_NAME_MAX_LENGTH` in
  `backend/infrahub/core/constants/__init__.py`);
- it adds that attribute, with a detail that holds a 70-character regular expression;
- it makes `InfraInterfaceL2.description` mandatory, so 28,904 nodes would fail;
- the first node that would fail has a 116-character name;
- schema change 00029 changes 1 node, and 00028 deletes 1 value, so every count of 1 shows;
- the failed load's run error names a 85-character kind and field path.

## Pass 1: Tidy (`emil-ui-polish`, `emil-surfaces`)

- **In dark mode, the details header and the section title bars are see-through.** The
  card header colour is 4.5 % white in dark mode, so the rows that scroll under a bar stay
  readable through it (lines 612, 767). Fixed: the bars draw the content colour under the
  header colour.
- **In dark mode, the dashed border of a staged change's version chip does not show**
  (line 246). Fixed: the dashed border uses the strong border colour.
- **A wrapped line of facts starts with a rule** ("│ Impact calculated…" at 1024 px,
  "│ deletes 3,377 values" in diff rows) (line 1037). Fixed: each value keeps its rule, and
  the line clips what is left of its edge, so the first value of each line shows no rule.
- **A kind card with a long name has an empty band under its header.** The hidden "View in
  the schema viewer" link wraps onto a second line and keeps its space (lines 930, 1383).
  Fixed with the critique finding on the same link: the link is an icon button that never
  wraps.
- Accepted: controls are smaller than the 40 px desktop minimum (section links 28 to 30 px,
  Recalculate 28 px, the information button 24 px, View the staged schema 20 px). The app
  uses the `@infrahub/ui` Button sizes xs and sm on every page, and the run is desk only;
  a larger size here alone would make the page differ from the rest of the app. To raise
  with the design system.
- Accepted: kind cards inside the details card use the app's Card radius instead of a radius
  derived from the 16 px gap. The cards are 16 px apart, so they read as separate surfaces,
  and the app nests Cards the same way.
- Accepted: "41,977 attribute values" wraps onto two lines in the Data deleted count at
  1440 px. It stays readable, and the four counts keep one height.

## Pass 2: Stress (`break-ui`)

- **Broken: 28,904 nodes that would fail render as 28,904 rows.** The page takes 8 seconds
  to load and holds 116,094 elements. Grouping the nodes also copied the list once per node
  (`context.tsx`, `ViolationList`). Fixed: each field lists its first 10 nodes, then
  "10 of 28,904 nodes listed" and a "List 100 more" button; grouping appends instead of
  copying. The page now loads in about 1 second.
- **Broken at 1024 px: a 102-character name makes the details header take 330 px of a
  545 px panel.** The version chip, the name (three lines), the status, the actions and the
  facts each take their own line, and the header stays in view, so about 60 px are left for
  the sections. Fixed:
  - the name breaks after an underscore before it breaks inside a word, stops at two lines,
    and shows in full on hover;
  - the version chip stays beside the name;
  - the actions sit beside the name when the panel is wider than 672 px, and under it when
    it is narrower;
  - the facts scroll away with the content; the name, the actions and the section links stay
    in view.
- **Ugly: counts of 1 read "1 kinds", "Migrates 1 nodes", "deletes 1 values",
  "1 migrations"** (lines 1071, 1086, 1109, 1203, 1481, 1497, 1609, 1625, 1815, 1825,
  2105). Fixed with one plural helper. The merge block said "The 0 schema changes before it
  pass" when the first change fails, and "the 2 after it is not checked" (lines 2827 to
  2885); fixed for 0, 1 and more.
- **Fragile: a list row cuts a long name with no way to read it** (line 468). Fixed: the
  full name shows on hover. The details panel shows it too.
- Accepted: the Schema changes list renders every schema change, and main gets one per
  schema load. The prototype has 30; the implementation uses the app's paginated list. To
  list in `05-implement.md`.
- Held up: the 85-character path in a run error, the regular expression in the After
  column, the migration path in the migration table, six-digit counts in the impact counts,
  the 116-character node name, and no sideways scroll at 1024 px.

## Pass 3: Critique (`emil-ui-review`)

- **Blocking: the tooltips that say why Apply, Discard and Recalculate are unavailable
  never show.** The buttons use `isDisabled`, which removes them from hover and from the tab
  order (lines 697, 1515, 1581, 1586). Checked in the browser: no tooltip on hover, and Tab
  skips the buttons. `dev/guidelines/frontend/component-patterns.md` asks for
  `isDisabledAndFocusable` in this case. Fixed: the tooltip now shows on hover and on
  keyboard focus.
- **Blocking: column labels fail the contrast floor.** The Change, Before and After labels
  and the migration table headings use `text-subtle-muted` (stone 400 on white, about 2.5:1;
  stone 600 on stone 900 in dark mode) (lines 1170, 1303). WCAG AA asks for 4.5:1. Fixed:
  they use the secondary text colour, and stay smaller than the rows they name. This answers
  the open question on the lighter labels.
- **Should fix: the details panel has no heading above its section titles.** The change
  name and the list title are plain text, so a screen reader that moves by heading lands on
  "Impact on data" with no heading for the change (lines 774, 2370, 2591, 2956). Fixed: both
  panel titles are second-level headings.
- **Should fix: "View in the schema viewer" shows only on hover or keyboard focus**
  (lines 930, 1383). Fixed: an icon button that is always shown, with a tooltip and the name
  "View <kind> in the schema viewer".
- **Should fix: Recalculate shows twice when the impact is out of date or failed**, once in
  the header and once in the banner or the empty state (lines 714 to 731). Fixed: the header
  names the state, and the panel holds the button.
- Nit, fixed: "deleted 3,377" in a run row was 12 px beside 14 px values (line 1984).
- Nit, fixed: "View the task" had an "opens in a new tab" icon but opens in the same tab
  (line 1709); it uses the arrow of the other links.
- Accepted: a section title that is pinned to an edge goes to its section instead of
  closing it, while it reports whether the section is open. Decided in round 21; pressing a
  pinned title still opens a closed section.
- Accepted: the chevrons rotate in 150 ms with the browser's `ease-out`. The app's other
  chevrons do the same, and reduced motion turns it off.

## Pass 4: Readiness (`emil-prep-for-prod`)

The marketing and SEO lane is skipped: the prototype has no marketing page. The mobile lane
is skipped: the run is desk only.

- Accessibility: the two blocking findings and the headings above.
- Performance: the 28,904 rows above.
- Forms: clean. Apply and Discard ask for confirmation.
- Stability and states: clean. Loading, empty, error, no permission, running, failed and out
  of date each render a message with a next step. Fixed: the apply progress label uses
  tabular figures.
- Motion: clean. The chevrons and nothing else move, with reduced motion handled.
- Theming: the two dark-mode findings above.
- Content and leftovers: accepted for the prototype and to list under *Replace* in
  `05-implement.md`: node links point to `#node`, View the task to `/tasks`, and the
  confirmation dialogs only close.

## Pass 5: By hand

- Tab order from the list: list rows, Discard, Apply to branch, the impact information
  button, Recalculate, the section links, View the staged schema, the section titles. The
  focus ring shows on each.
- Dark mode: found the see-through bars and the hidden dashed border, both fixed; checked
  again scrolled.
- 1024 px: no sideways scroll with demo data or the worst case (page width 1024 px).
- Every state renders in rev 7 with no console error: staged, applying, impact running,
  failed, out of date and not matching, empty, loading, error, no permission, an applied
  change, a failed load, the proposed change before and after a rolled-back merge, branch
  details and the schema viewer.
- Accepted for the owner to decide: at 1024 px, the part of the header that stays in view
  is still about 200 px of the 545 px panel (the name on two lines, the status, the actions,
  and the section links on two lines). Hiding the links band below a panel width, since the
  section titles stay on screen, would save about 75 px.
