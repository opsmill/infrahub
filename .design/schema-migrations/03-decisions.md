# Decisions: the branch Schema tab direction

Prototype: `dj.variant=collapsible-sections`, rev 9: One list (chosen in round 15) with
collapsible sections, header links and section titles always on screen, the fixes of the
phase 4 review ([04-review.md](04-review.md)), and the requirements that rev 7 missed
([04-coverage.md](04-coverage.md)). Removed from the
panel at the owner's request, and kept in git:
- Staged tab (`schema-tab` revs 1 to 11), Review page and One list revs 1 to 3, at
  `ec383abdf9`;
- One list rev 4, Section links and Collapsed kinds, at `e0dc74065a`;
- Titles at the edges, Short sections first and Section tabs, at `bc67d20136`.

Placement map:
[placement-map.html](placement-map.html).

On 2026-11-16 the owner first picked the schema page for the schema changes and the staged
change (combined revs 1 and 2, kept in git at `f946a7c71c`). After reviewing the placement
map, the owner moved them to the branch Schema tab. The sections below record the decisions
that still hold.

## Where the views live (revised 2026-11-16)

- **The branch Schema tab gets three sub-tabs: "Schema changes", "Staged" and "Diff".**
  "Diff" is what the tab shows today. The stored schema changes are the steps that produced
  that diff, so they sit next to it.
- **The proposed change Schema tab gets "Schema changes" and "Diff"**, the same structure as
  the branch without "Staged", because a staged change is not part of a merge. When the
  branch has a staged change, the merge block says "1 staged schema change, not merged".
- **A sub-tab name shows the same content in every place (revised 2026-11-17, round 4).**
  "Schema changes" in the proposed change uses the branch's list and details panel, because
  the steps of a merge are the branch's schema changes run again on main. The proposed
  change adds information and replaces nothing:
  - the block above the list shows main's revision now and after the merge, the result of
    the check against main, and "Check again", in the place where the branch shows its
    revision;
  - each row adds the version the change gets on main and its result: Passes, Would fail
    or Not checked, or after a rolled-back merge, Rolled back, Failed or Not run;
  - the details panel adds a "Merge into main" section, with the nodes that would fail for
    the selected change;
  - the list keeps the branch's order, newest first, and failed loads are labelled "not
    merged".
  Rev 1 showed a separate list of numbered steps that expanded in place. It was rejected
  because the same records had two layouts, and the reviewer could not view the runs of a
  change.
- **Main gets the Details and Schema tabs** on its branch page, with "Schema changes" and
  "Staged" and no "Diff". Today the branch page shows no tabs on main
  (`frontend/app/src/pages/branches/details.tsx:49`).
- **The schema viewer has one toggle, "List | Graph | Staged" (revised 2026-11-17, round 4).**
  List is the schema in use, as today; rev 2's "Current" was the same view, so it is
  removed. Staged uses the List layout for the schema after the staged change: "Changed
  kinds only" is on by default, changed and removed kinds are marked, and old values are
  struck through. Graph does not change. Staged reads the schema API with `staged=true`,
  which the engineering investigation plans "so the front-end project can add one parameter
  to the calls it already makes".
- **The schema viewer and the branch Staged sub-tab show different things.** The schema
  viewer shows a kind in full after the change. Staged shows what changes and its effect on
  data. Each one links to the other for the same kind.
- **The branch Details tab keeps two rows**, "Schema revision" and "Staged schema change",
  that point to the Schema tab (round 1, note 4).
- **The only panel is the existing page layout**: no side panel, no new branch tab, no new
  menu entry.

## Page structure: one list (decided 2026-11-18, round 15)

The owner chose **One list**: the staged change is the first row of the Schema changes list,
and its impact, Apply and Discard are in the details panel. The owner's reason: the user
views where the change is in the workflow (staged, then applied) in one list, without a
separate view to open.

Rejected:
- **Staged tab** (`schema-tab` rev 11): three levels of tabs before the impact, and the
  staged change and the applied changes on different sub-tabs.
- **Review page** (`review-page` rev 1): a separate page for the staged change, so the
  staged and applied changes still live in two places, with one more click to reach the
  impact.

Both stay in the panel unchanged. The comparison made in round 14 follows. Kind cards, rows,
empty states, links and separators are rev 11's in all three.

| | Staged tab (`schema-tab` rev 11) | One list (`one-list` rev 1) | Review page (`review-page` rev 1) |
|---|---|---|---|
| Branch sub-tabs | Schema changes, Staged, Diff | Schema changes, Diff | Schema changes, Diff |
| Where the staged change is | Its own sub-tab | First row of the Schema changes list, in a "Staged" group, selected by default | A bar above the Schema changes list; Review opens a page at `/branches/<branch>/schema/staged` |
| Where the impact is | Staged sub-tab, with "Schema difference" and "Would fail" tabs | Details panel, with "Impact on data", "Schema difference" and "Would fail" as sections one under the other | Review page at full width, with "Schema difference" and "Would fail" tabs |
| Where Apply and Discard are | Staged record header | Details panel header, which stays in view while the panel scrolls | A bar at the bottom of the review page, with what Apply runs and deletes |
| Tab levels to reach the impact | 3 | 2 | 2 (on its own page) |
| After Apply | The change moves to Schema changes as 00031; Staged shows "applied" | The "Staged" group shows "Nothing staged" and 00031 is in "Applied", in the same list | The bar goes away; the review page shows "applied" with a link to 00031 |
| Proposed change | Schema changes, Diff; the staged change is a link to the branch | The same list, with a "Staged, not merged" group | Same as Staged tab |
| Main | Schema changes, Staged | The list, no sub-tabs | The list, no sub-tabs |

Both new directions keep the selected schema change in the page address (`change` on the
branch and main, `pc_change` in the proposed change), so a link opens that change.

Both new directions take the height of the panel's pane, as the app gives a page the
window's height. Rev 11 does not: the whole page scrolls, so nothing stays in view.

Costs to weigh, from the round 14 assessment:
- One list: the impact gets the details panel's width, about 810 px at 1440 px and 390 px
  at 1024 px, where the four counts wrap to two rows and the actions wrap under the name.
- Review page: one more page and one more click, and the staged and applied changes still
  live in two places.

### The version of a staged change and a failed load (one-list rev 2, round 15)

A schema change gets its version only when it is applied. Rev 1 showed "-" in the version
chip of the staged row and of failed loads, which reads as missing data (owner).

- **The staged row shows the version it gets when applied**, 00031, in a chip with a dashed
  border and muted text, and says "Becomes 00031 when applied". In a proposed change it says
  "Becomes 00031 on the branch when applied", next to rows that say which version each
  change gets on main. The details header shows the same dashed chip. The number is the
  branch's revision plus one, as the applying message already says ("The branch moves to
  revision 00031"). The investigation does not say whether the API returns it before the
  apply, so the page calculates it.
- **A failed load shows a red chip with a cross** (rev 3), the same width as a version chip,
  in its row and its details header, and says "no version" after its date, because it never
  gets one. Rev 2 showed no chip, which left the row without a version or a badge (owner,
  round 16).
- **The staged row no longer shows when it was staged**, to keep it to three lines at 320
  px; the details header still shows it.

### Font of names and numbers (one-list rev 4, round 16)

The app uses a monospace font in about 10 places, for commit hashes, node IDs and error
text, and not for names (owner). From rev 4:
- names of schema changes, kinds and fields, and version numbers, use the app's font;
- version numbers use tabular figures, so they line up in the list;
- commands to copy and node IDs stay monospace, as in the app.

Rev 3 keeps the monospace font for comparison.

## Header of the details panel (2026-11-18, round 22)

Rev 5 and rev 6. The header has three bands:
- the change: version chip, name and status, with Discard and Apply to branch (or the apply
  progress) on the right;
- one line of facts, separated by thin rules: when it was staged and on which revision,
  then the impact calculation with an information tooltip and Recalculate. While applying:
  since when, the revision the branch moves to, and View the task;
- the section links, each with the icon of its section title, and View the staged schema at
  the end (rev 6).

The impact line is in the header because the numbers Apply relies on come from that
calculation. Problems stay in the panel as banners: the staged schema no longer matches the
branch, or the impact is out of date. The header shows them in colour too.

Header knobs, so the owner can choose what it shows (defaults in brackets): impact
calculation (in the header), when staged and on which revision (on), View the staged schema
(on), number of operations (off, it repeats the Schema difference count), previous schema
change (off), links to the sections (on).

A rule between two facts stays with the value after it, so a wrapped line never ends with a
rule (rev 6), and the line clips the rule of its first value, so a wrapped line never starts
with one either (rev 7).

### What stays in view (rev 7, phase 4 review)

- **The name band and the links band stay in view; the facts band scrolls away with the
  content.** At 1024 px with a long name, the whole header took 330 px of a 545 px panel.
  The knob "Header: facts stay in view when scrolling" (off) brings back the rev 6
  behaviour. Without the links band, the facts stay with the name.
- **The name breaks after an underscore, stops at two lines, and shows in full on hover.**
  The version chip stays beside it, and the status badge follows it or goes to the next
  line.
- **Discard and Apply to branch sit beside the name when the panel is wider than 672 px**,
  and under it when it is narrower.
- **When the impact is out of date or failed, the header names the state and the panel
  holds Recalculate**, so the button is not shown twice.

### Type scale (rev 6)

The section titles (16 px) were larger than the name of the change (14 px) (owner). Rev 6
uses one scale, in the app's font:

| Size | Weight | Used for |
|---|---|---|
| 20 px | 700 | Page title (the app's) |
| 18 px | 600 | The two panel titles: the list header ("Revision 00030") and the change name in the details header, with a 14 px version chip; the numbers of the impact counts |
| 16 px | 600 | Section titles (Impact on data, Schema difference, Would fail, Runs, Merge into main) |
| 14 px | 600 | Card titles: kind names, would-fail fields |
| 14 px | 400 or 500 | Text: list rows, facts, links, tabs, node names |
| 12 px | 400 | Secondary text: dates under a row, labels of the counts, column labels, changes in a kind |

Column labels use the secondary text colour, like the rest of the secondary text, from
rev 7. The lighter colour of rev 6 was about 2.5:1 on white, under the 4.5:1 that WCAG AA
asks for.

## Order of the details panel: links and titles always on screen (decided 2026-11-18, round 21)

The owner chose the header links of collapsible-sections rev 3 with the always-visible
titles of edge-titles, in collapsible-sections rev 4:
- the details header stays in view and links to every section with its count; a link opens
  its section, scrolls to it and highlights its title for 1.2 seconds; no link is shown as
  the current one;
- every section title is always on screen: in place, stacked under the header once its
  section is passed, or stacked at the bottom edge until it is reached;
- a title stacked at an edge takes the viewer to its section; a title in place opens or
  closes it;
- titles are 44 px bars with the card header's grey background and 16 px semibold text
  (owner: "a bit more visible");
- in a proposed change, Merge into main is a section like the others, and the details card
  grows with its content so the header and titles stick to the area that scrolls;
- each section's content has its own stacking context, so the raised parts of kind cards
  stay below the titles (owner).

Rejected: Short sections first, because the short section is not always short (owner);
Section tabs.

### The comparison, round 20

Before the choice: In collapsible-sections rev 2, the owner found that the first link stays
highlighted when every section is in view, and that the link of a section already in view
does nothing. The highlight shows where the viewer is; the need is to know which sections
exist and what they hold, for a panel with two important sections (owner). Four directions
in the panel:

| Direction | How the viewer knows a section exists | Both sections in view at once | Cost |
|---|---|---|---|
| Collapsible sections with links, rev 3 (`collapsible-sections`) | Links with counts in the header; a link opens its section, scrolls to it when needed and highlights its title for 1.2 seconds; no link is highlighted as current | Yes | The links repeat the section titles when the sections are closed; the header is tall at 1024 px |
| Titles at the edges (`edge-titles`) | Every section title is always on screen: in place, stacked under the header once passed, or stacked at the bottom edge until reached | Yes | Up to 3 title lines stay pinned; less common in web applications |
| Short sections first, rev 2 (`short-first`) | Would fail or Runs comes first; Would fail shows 2 fields and "Show all" | Yes | Fixed order; one click to view every failing node |
| Section tabs (`section-tabs`) | Tab labels with counts | No | A third level of tabs |

### Collapsible sections with links (chosen in round 19, reopened in round 20)

The owner chose to combine collapsible sections and links in the header, so the header
shows every section with its count and the viewer does not miss one (owner). In
collapsible-sections rev 2:
- the header of the details panel stays in view and links to each section: Impact on data,
  Schema difference and Would fail for the staged change; Merge into main (proposed
  change), Schema difference and Runs on this branch for the others;
- a link opens its section when it is closed and scrolls to it; the link of the section in
  view is highlighted;
- each section title opens and closes its section, shows a summary when closed, and stays
  under the header while its section scrolls;
- what the viewer opens or closes stays so on other schema changes;
- the schema difference starts closed above 5 kinds (knob "Schema difference starts").

Cost: at 1024 px, the header takes about half the height of the details panel, because the
name, the actions and the links wrap.

Rejected, in git at `e0dc74065a`: one-list rev 4 (current order), Short sections first,
Section links alone, Section tabs and Collapsed kinds.

### The comparison, round 17

Before the choice: With many changes, the schema difference fills several screens, so Would fail
(staged change) and Runs (applied change, failed load) are at the bottom of the details
panel (owner). Six directions, all made from one-list rev 4:

| Direction | Staged change | Applied change or failed load | Cost |
|---|---|---|---|
| One list rev 4 (current order) | Impact on data, Schema difference, Would fail | Schema difference, Runs | Would fail and Runs at the bottom |
| Short sections first (`short-first`) | Impact on data, Would fail, Schema difference; "View the nodes" under the would-fail count | Runs, Schema difference | A long Would fail list pushes the schema difference down |
| Section links (`section-links`) | Links under the name: Impact on data, Schema difference, Would fail | Links: Merge into main (proposed change), Schema difference, Runs; the header now stays in view | The header is one line taller |
| Section tabs (`section-tabs`) | Impact on data, then tabs: Schema difference, Would fail | Tabs: Schema difference, Runs; a failed load opens on Runs | A third level of tabs |
| Collapsed kinds (`collapsed-kinds`) | Kinds collapsed to one line each, except a kind opened from a link or a change with one kind | Same | One more click to view the changes of a kind |
| Collapsible sections (`collapsible-sections`, round 18) | Each section title opens and closes its section and stays under the header while the section scrolls; a closed section shows a summary; the schema difference starts closed above 5 kinds (knob) | Same, with the last run in the closed Runs title; the header stays in view | One more click to view a closed section; a third toggle style |

In the proposed change, the merge block sits above the list, so the whole area scrolls and
the header of the details panel does not stay in view, in every direction. Section links
still scroll to their section there.

## Names (revised 2026-11-16)

- **The list is called "Schema changes"**, the backend's name ("stored schema changes" in the
  investigation). "Stored migrations" (INFP-719, journey 2.5) was rejected: in the backend a
  migration is one step inside a schema change, and a label change is a stored schema change
  with no migration.

## Links between screens (2026-11-17, round 4)

Every place that shows part of a record links to the place that shows more of it:

- **Branch Details tab:** "View in Schema changes" opens the newest schema change; "View in
  Staged" opens the staged change.
- **Revision block:** "1 staged schema change" opens Staged; "1 failed load" opens Schema
  changes with the failed load selected.
- **Schema change details** (branch and proposed change): each changed kind links to the
  schema viewer List with that kind selected.
- **Staged:** "View the staged schema" opens the schema viewer Staged; each kind heading in
  the schema difference opens the schema viewer Staged on that kind; while applying, "View
  the task" opens the task pages; once applied, "View it in Schema changes" selects the new
  schema change.
- **Schema viewer:** in Staged, "View the impact on data" opens the branch Staged sub-tab,
  scrolled to the selected kind; in List, a kind with staged operations shows "View in
  Staged".
- **Proposed change:** "1 staged schema change, not merged" opens the branch Staged sub-tab.

Not known: whether each past run keeps a link to its task, so only the running apply links
to the task pages.

## Same data, same component (2026-11-17, round 6)

Rev 3 drew the same records differently in each view. Rev 4 uses one component for each
kind of data, and takes it from the app where the app has one:

| Data | Component in rev 4 | From the app |
|---|---|---|
| Section or panel | `Card`, `CardHeader`, `CardContent` | `@infrahub/ui`, as on the branch Details tab |
| A schema change | version chip, then its name, in every list, header and message | New |
| Any status: schema change, run, migration, merge check | one status badge with one label and colour per status | `Badge` |
| What a schema change changes | one row per change: Change, Before, After, with the added, removed and updated colours | `DiffRow` and `DiffBadge`, from the Diff tab |
| What a change does to data | one line: nodes, progress, deletions, nodes that would fail | New |
| A list beside a details panel: schema changes, kinds | one list panel with the same header, groups and rows | New |
| The top of a record: staged change, merge | title, status, facts, actions, then a message | New |
| A screen with nothing to show | icon, title, what happened, what to do next, actions | Same look as the diff's "No changes detected" |
| A command to run | the command with a copy button | `CopyToClipboardButton` |
| A run | an accordion row with its migrations | `Accordion` |

## Kind cards of the schema difference (2026-11-18, round 11)

- **The header line says what the kind's changes do**, so a collapsed card can be read
  without opening it: the status icon, the kind name, the number of changes, then the
  effect on data ("Migrates 1,302 nodes", deletions, "3 would fail").
- **The status is an icon before the name** (the Diff tab's badge without its word, with
  the word in a tooltip and for screen readers), so every kind name starts at the same
  place. Rev 8 put the word badge first, so names moved with its width.
- **Every change has a verb:** "attribute added", "optional changed", "label changed",
  "kind removed, with every node". Rev 8 said only "optional" or "label".
- **"View in the schema viewer" is an icon button at the end of the header line, always
  shown** (collapsible-sections rev 7). It showed only on hover or keyboard focus, and with
  a long kind name its hidden space left an empty band under the header.
- **The effect on data starts with a verb:** "Migrates 1,302 nodes"; "Migrated" once
  applied; "27,850 of 48,213 nodes migrated" while applying. Rev 8 said "1,302 nodes".
- **"3 would fail" is a link to the Would fail tab** in Staged.
- **A row opens to a compact table** at the row's text size, indented under the row with a
  line on its left: kind and field first, then the migration, nodes, deletions, nodes that
  would fail (when any) and the status while applying. Rev 8 opened the larger table used
  for runs.

Revised 2026-11-18, round 12 (rev 10):

- **"View in the schema viewer" shows only while the kind header is hovered or holds keyboard
  focus**, so 19 cards no longer repeat it.
- **Kinds stay in the order of the operations** (owner).
- **An empty value is "-"**, the same character the Diff tab shows for a value that does not
  exist. This applies to values in the schema difference, not to the version of a schema
  change (round 15, below). Rev 9 used "—". The Before column stays on every row, for the same columns
  everywhere (owner).
- **The column labels (Change, Before, After, and the migrations table headings) are
  lighter and shorter.** They use the app's `text-subtle-muted`, which is below the WCAG
  contrast for text on white; the app uses it for secondary labels in 102 places.
- **"would fail" opens the Would fail tab on the group of that field**, outlined for 1.6
  seconds.
- **The Would fail tab is a separate view, not a highlight:** it lists each node to fix
  before applying, grouped by check and field, with a link to the node and the reason, and
  the count of nodes on kinds the viewer cannot view. The schema difference shows only the
  counts and links to it.

Revised 2026-11-18, round 13 (rev 11):

- **A thin vertical rule separates each value** in a kind header (kind, changes, migrated
  nodes, deletions, would fail) and in the data line of each change.
- **Every link has the app's link look:** a dotted underline that turns solid on hover, as
  in `frontend/app/src/shared/components/ui/link.tsx`. This includes "would fail", "Expand
  all", "View in the schema viewer" and the links between screens. Rev 10 underlined links
  only on hover.

## Accordion toggles (2026-11-17, round 7)

The kind cards, the rows of the schema difference and the runs use the app's `Accordion`
(`frontend/app/src/shared/components/display/accordion.tsx`), as the Diff tab does. In rev 4:

- the toggle is a `div` with a click handler, so a keyboard cannot reach it and a screen
  reader does not announce it, or whether it is open (no `aria-expanded`);
- hovering a row changes nothing; only the cursor changes;
- the row chevron is centred on a two-line title, and nothing says what the row hides.

Rev 5 replaces it in the prototype with a button:

- a real `button` with `aria-expanded` and `aria-controls`, named after what it opens
  ("InfraInterface, 1 change", "Migrations for mtu_legacy");
- the whole header or row is clickable, through the button's overlay; links inside the
  header stay clickable;
- a hover background, a focus ring around the whole header, and a chevron that turns in
  150 ms (no animation when reduced motion is set);
- "Collapse all" and "Expand all" above the kind cards.

**Two toggle levels (owner, 2026-11-17, round 8).** The owner picked the chevron in the
left gutter for rows, on condition that it looks different from the kind card's chevron
above it. In rev 6:

- a card or a list item (a kind card, a run) opens with a chevron in a small bordered box;
- a row inside an open card opens with a smaller caret with no box, in a muted colour;
- both sit on the same vertical line, so the row's caret reads as part of the card.

Rejected: "labelled rows" (a "Show 2 migrations" button under each row), because rows
would use a different control from cards; one chevron for both levels (rev 5), because
the two levels looked the same.

The "Accordion toggle" knob is removed now that the owner has decided: rev 4 shows the
app's toggle, rev 5 one chevron for both levels, and rev 6 the two levels.

Not decided: whether the handoff changes the shared `Accordion`. It is used in 16 places,
the Diff tab among them, so a fix there also fixes keyboard access in those places.

## Empty and waiting screens (2026-11-17, round 6)

Each one says what happened and offers the next action when one exists:

| Screen | Says | Action |
|---|---|---|
| Schema changes, none on the branch | The branch uses main's schema at 00024; each load adds a schema change | The load command, with copy; "View the schema" |
| Staged, nothing staged (branch or main) | Stage a file to view its changes and effect on data | The stage command, with copy |
| Staged, just applied | The change became revision 00031 | "View it in Schema changes" |
| Staged, impact calculating | The counts and the difference appear when it ends | Discard stays in the header |
| Staged, impact failed | The error | Recalculate |
| Would fail, no node | Infrahub checked every node, and when | None |
| Proposed change, no schema change | Merging changes data only; main stays at 00027 | None |
| Schema viewer Staged, nothing staged | Stage a file to view the schema it would produce | The stage command; "View List" |
| Schema viewer Staged, just applied | List shows the schema with the change | "View List" |
| Any view, loading | "Loading the …" | None |
| Any view, error | Nothing changed | Try again |

## Layout and surfaces

- **Sections are white surfaces** (`bg-content`, border, large radius) on the grey panel
  (`Card variant="panel"`), as on the branch details page (round 1, note 3).
- **The schema viewer header has two lines**: "Schema" with the kind count, and the branch
  name with its revision below it. The separate "Branch selected in the header" line is
  removed (round 1, note 5).
- **No revision block above the sub-tabs (revised 2026-11-17, round 6).** Rev 3 repeated it
  above Schema changes and Staged, and it repeated the first row of the list and the
  Staged header. The revision is now the header of the Schema changes list ("Revision
  00030, branched from main at 00024"); the Staged header says which revision the change
  was staged on; the Staged count and the "Failed loads" group replace its two links.
- **A card that holds other cards has a white body (2026-11-18, round 9).** The Staged
  impact card ("Schema difference | Would fail") had a grey body, the same grey as the page
  behind it. It is now white, like the schema change details panel that holds the same kind
  cards.
- **The kind cards of a schema difference are 12 pixels apart (2026-11-18, round 10)**, the
  same as the padding between them and the sides of the impact card, so the spacing is even
  on every side.
- **The "Staged" sub-tab is always there**, so the tab row keeps its shape. It shows a count
  when a schema change is staged, and an empty state explains how to stage one.
- **The schema changes list is 320 pixels wide** (knob `listWidth`, range 256 to 448).

## Content

- **The impact has two sections, "Schema difference" and "Would fail".** The separate
  Migrations list is removed: each operation in the difference shows the migrations it
  creates, and any migration left over appears under "Migrations Infrahub adds".
- **The schema difference looks like the Diff tab (revised 2026-11-17, round 6).** One card
  per kind with the Added, Removed or Updated badge, then one row per change with three
  columns: the field and what changes, the value before, the value after. Under the field,
  one line gives the effect on data. A row with migrations opens to list them. The same
  component shows the staged change, a stored schema change, and a schema change in the
  proposed change.
- **"Data deleted" shows three counts** (nodes, attribute values, relationship peers),
  because one sum adds different units.
- **"Nodes that would fail" says how many are listed and how many are on a kind the viewer
  cannot view.**
- **The impact line says "Data changed on the branch since then is not counted"**, because
  the investigation does not decide how to detect data changes.
- **Runs are labelled "Run 1", "Run 2"**, because no field says whether a run was a load, a
  rebase or a merge.
- **Failed loads are grouped above the applied schema changes**, because on main they are
  never deleted and would otherwise sit between applied changes.
- **The link between an operation and its migrations is built in the frontend** from the
  schema it already loads: kinds that inherit a generic, profile kinds, and uniqueness
  constraints. The investigation defines no such link.

## Progress

- **No new button in the app header.** Applying, recalculating and merging run as tasks,
  and the existing task status button already shows tasks running on the branch.
- **Staged keeps one layout while the change is staged, applying and applied (revised
  2026-11-17, round 4).** Rev 2 replaced the whole view with a progress list while
  applying. Now only these parts change:
  - the status badge: Staged, then Applying;
  - the actions: Apply and Discard, then a bar of migrations ended out of the total, with
    "View the task";
  - each migration in the schema difference: its node count, then nodes done out of the
    total, a check when it ends, or "waiting";
  - "Would fail": its list, then 0, because the apply starts only after the check passes.
  Once applied, the sub-tab is empty and links to the new schema change. The sub-tab is
  always named "Staged"; rev 2's "Staged · applying" label is removed.
- **One activity button for tasks, Git sync and schema is a separate design run**, because
  it changes the app shell for every feature (owner, 2026-11-16).

## Permissions

- **Without the Manage schema permission**, Apply, Discard and Recalculate are dimmed and
  do nothing, and a tooltip names the permission. They stay focusable
  (`isDisabledAndFocusable`) so the tooltip shows on hover and keyboard focus; disabled
  buttons hid it (fixed in collapsible-sections rev 7). The investigation requires `MANAGE_SCHEMA`, plus
  `EDIT_DEFAULT_BRANCH` on main.

## Schema viewer: the schema page's list and details (rev 10, round 25)

- **The same list as the schema page**: kinds grouped by namespace, with the search field
  and Collapse all. Each kind shows its icon, the namespace badge and the label, Node or
  Generic, and its description, as on /schema. The kind name (for example `InfraDevice`)
  is added under the label, because the Schema changes list and the migrations name
  kinds, not labels.
- **The same details card**: the namespace and Node badges with the ID, the icon, label
  and description, then the Properties, Attributes and Relationships tabs. The
  attributes and relationships use the schema page's own components.
- **Changes on the list**: in Staged, each changed kind has the number of its operations,
  or Removed or Added; a namespace shows how many kinds it lists. Changed kinds only
  stays on by default.
- **Changes in the details**: each tab shows how many fields change. A changed field is
  outlined and open, and shows the value before, struck, then the value after. An added
  field is outlined in green, a removed one in red and closed. A tab with changes opens
  first.
- **Inherited fields**: a kind lists the fields of the generic it inherits from, marked
  "Inherited from", so a change to `InfraInterface` shows on `InfraInterfaceL2`. The list
  counts only the kind's own operations; the details card names both.
- **The rows stay as tall as on the schema page** (about 90 pixels). A compact row, with
  the label and the kind only, fits twice as many kinds; not built, offered to the owner.

## The list stays in view in the proposed change (rev 9, round 24)

In the proposed change the whole tab scrolls, so the details header stayed at the top while
the Schema changes list scrolled away (owner: "not consistent"). The whole list now stays at
the top of the tab, at the tab's height, and scrolls inside, rather than only its header
staying: a header that stays while its rows scroll away would show a title over nothing. On
the branch and main, the page fits the window, so both cards already scroll inside.

## Requirements added in rev 8 (round 23)

The owner asked to check the design against INFP-719 and the investigation, edited on
2026-11-19 ([04-coverage.md](04-coverage.md)). Rev 8 adds:
- **A staged change blocks the merge.** The proposed change says so above the merge result,
  rather than "not part of this merge" (rev 7), which implied the merge goes ahead.
- **A failed apply** keeps the Staged badge and adds a red message and an "Apply failed"
  fact, rather than a new status: the investigation keeps the change `staged`.
- **The checks that pass** are counted in one line and listed on request, rather than
  listed by default, so the nodes that fail stay first.
- **A stopped merge has one action, Roll back the merge**, with a confirmation, rather than
  a preview step: the recovery preview only reports whether a rollback is possible.
- **A merge that runs and a load that runs** reuse the apply progress: a bar of migrations
  or schema changes ended, and nodes per migration. A running load shows a clock in place
  of its version, because it gets one only when it ends.
- **A schema change skipped at merge** is a row in its own group on main, rather than a run
  hidden in another change: main keeps no schema change for it.

## Nodes that would fail (rev 7, phase 4 review)

- **Each field lists its first 10 nodes, then "10 of 28,904 nodes listed" and "List 100
  more".** Listing every node rendered 28,904 rows and took 8 seconds. The count badge
  keeps the full number. The implementation needs the API to return the nodes of a field
  page by page, with the total.

## Counts

- **A count of 1 takes the singular**: "1 kind", "Migrates 1 node", "deletes 1 value". The
  merge block words 0, 1 and more schema changes before and after the one that fails.

## Rejected in round 1

- **A "Schema changes" tab on the branch** (direction "On the branch"): it sat next to the
  existing Schema tab and confused the owner (note 1), and main has no tabs.
- **A side panel opened from a header button** (direction "In the review"): at about 670
  pixels the impact tiles wrapped, the panel covered the branch page, and the "Schema
  00030" button did not say what it opens (round 1, note 4). Round 2 declined it again: it
  does not work on small screens.
