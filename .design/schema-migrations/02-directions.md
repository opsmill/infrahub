# Directions: where the schema migration views live

Prototype: `/_proto/schema-migrations` in the running app. The `Screen` knob switches
between the seven screens, and the `Impact calculation` knob switches the state of the
impact (`done`, `running`, `failed`, `out of date`, `conflict`).

The three directions show the same records and the same inner views. They differ in where
the views live, and so in who reaches them and when.

## Shared by every direction

### Names and records

The views use the investigation's names (owner decision, 2026-11-16). They show only the
fields that [the investigation](https://app.notion.com/p/402228b830258193b43ed097d965f633)
defines:

- **Schema change** (the changes of one load):
  - name, `<version>_<summary>`, for example `00030_infrabgpsession_add_bfd_profile`;
  - version, a number, or none when it is staged or failed;
  - status: `staged`, `running`, `applied` or `failed`;
  - parent, branch, time loaded, time applied on main;
  - operations: each one names a kind, an attribute or relationship, a property, and the
    values before and after.
- **Application** (one time a schema change runs on a branch): status (`running`,
  `applied`, `failed`, `rolled back`, `skipped`), time, error, and the operations left out.
  The views label applications "Run 1", "Run 2", because no field says whether a run was a
  load, a rebase or a merge.
- **Migration** (one operation on the nodes of one kind): name, kind and field, status
  (`waiting`, `running`, `applied`, `failed`, `rolled back`), nodes to change, nodes done,
  error.
- **Staged impact**, for a staged schema change only:
  - the migrations, with nodes per kind and deletion counts;
  - the nodes that would fail, grouped by check, with the check's message;
  - the checks that passed;
  - the calculation status and time, whether it is out of date, and conflicts with the
    branch schema.

### Inner views used in every direction

- **Revision line**: version and name of the last applied schema change, when it was
  applied, the number of failed loads, and a "1 staged schema change pending" or "Applying"
  badge.
- **Staged summary**: operations, migrations and the number of kinds, nodes touched, nodes
  that would fail (with the count the viewer cannot view), and data deleted, split into
  nodes, values and peers.
- **Schema difference**: operations grouped by kind. Next to each operation, the migrations
  it creates, with node counts, deletions and the number of nodes that would fail.
  Migrations on kinds that inherit a changed generic, on profile kinds, and on uniqueness
  constraints are linked to the operation through the schema the frontend already loads.
  Any migration left over is listed under "Migrations Infrahub adds".
- **History**: failed loads in their own group, then applied schema changes, newest first.
  Each one opens to its operations, its parent and its runs. Each run opens to its
  migrations.
- **Run progress**: migrations ended out of the total, then each migration with nodes done
  out of the total.
- **Replay list** (proposed change): each step with its version on the branch and its
  version on main (`00025 → 00028`). In review, each step shows Passes, Would fail or Not
  checked. After a failed merge, each step shows Rolled back, Failed or Not run.

### Worst-case data in the mock

- A branch name of 61 characters.
- A kind name of 50 characters (`InfraCircuitTerminationEndpointInterfaceAssignment`).
- A staged schema change with 23 operations, 11 migrations and 67,090 nodes, which
  deletes 87 nodes, 41,977 values and 18 peers.
- Violations on a node with no display label.
- 41 violations on a kind the viewer cannot view.
- Main with 28 applied schema changes, one of them created at the upgrade, and two failed
  loads.
- A label-only change with no migration.

## On the branch (`dj.variant=branch-tab`)

**Bets on:** schema changes belong to a branch, like its data and files. The branch details
page gets a "Schema changes" tab. The tab shows the revision line, then the staged schema
change as a card that opens to Migrations, Schema difference and Would fail, then the
history. The proposed change Schema tab lists the replay above the existing node diff.

**Costs:**

- Main needs tabs on the branch details page, which today shows none on the default branch.
  The direction adds Details and Schema changes for main only.
- The branch page grows long: the revision, the staged card and 6 to 30 history rows on one
  scrolling page.
- The schema page and the branch page now both show schema information for a branch, in
  different places.

**Suits:** a schema owner who works one branch at a time, and opens the branch to see
everything about it.

## On the schema page (`dj.variant=schema-page`)

**Bets on:** schema changes belong to the schema. The schema page gets History and Staged
next to List and Graph. Both follow the branch selected in the header, so main works like
any branch.

- History is a list on the left and the selected schema change on the right.
- Staged is one page: the summary, then the schema difference beside the nodes that would
  fail.
- The proposed change Schema tab shows a short replay list with a link to the history on
  the schema page.

**Costs:**

- The views depend on the branch selector. A reviewer who comes from a proposed change has
  to switch branch to view the history.
- The Staged button is shown only when a schema change is staged, so the toggle group
  changes width.
- The prototype cannot set the real branch selector. The header shows `main` while the page
  shows the feature branch.

**Suits:** a schema owner who thinks in schema terms and moves between branches, and main.

## In the review (`dj.variant=review`)

**Bets on:** schema changes matter most when someone decides to merge.

- The proposed change Schema tab splits into "Schema changes" and "Node diff".
- Schema changes opens on the merge plan: main's version now and after the merge, the
  result of the check against the current main, and the replay list.
- Elsewhere, a "Schema 00030 · 1 staged" button in the branch header opens a side panel with
  Staged and History.

**Costs:**

- The staged impact and the history get a panel about 670 pixels wide. The summary tiles
  wrap, and long kind names break across lines.
- The side panel covers the branch page. Nobody can compare the impact with the data on the
  branch side by side.
- Main has no proposed change, so main's history is only in the side panel.

**Suits:** the reviewer, and teams where schema changes always go through a proposed
change. This matches the riskiest assumption in the brief: if schema owners do not open the
UI, the reviewer is the main user.

## Not decided in this phase

- Where progress shows outside these views. Every direction shows it in place of the staged
  schema change. A status button in the app header, next to the task button, is planned for
  phase 3.
- Whether the backend can return the link between an operation and its migrations. The
  prototype builds the link in the frontend from the schema (generics, profiles,
  uniqueness constraints).
