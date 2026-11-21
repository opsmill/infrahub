# Coverage of the requirements

Checked on 2026-11-19 against:
- [INFP-719](https://opsmill.atlassian.net/browse/INFP-719), the product card, last updated
  2026-11-16;
- the [engineering investigation](https://app.notion.com/p/402228b830258193b43ed097d965f633),
  status Approved, last edited 2026-11-19, after the brief was written (2026-11-16);
- the [user journey](https://app.notion.com/p/3fd228b83025813392f1f29b5184fb11), last edited
  2026-10-18.

Where the sources disagree, the design follows the investigation (owner's decision,
2026-11-16). Rev 7 was checked first; rev 8 adds what rev 7 missed.

## Covered

| Requirement | Source | Where in rev 7 |
|---|---|---|
| View the difference between the branch schema and the staged schema | INFP-719; investigation D1 | Staged change, Schema difference section: one card per kind, one row per operation, before and after |
| View the migrations a staged change would create, with node counts per kind | INFP-719; D1 | Each operation row lists its migrations by kind and field, with node counts; Impact on data counts |
| View the nodes that would fail, with the reason, as a list | INFP-719; D1 | Would fail section, grouped by check and field; 10 nodes per field, then "List 100 more" |
| A viewer without `view` on a kind gets the count only | D1 | "You do not have permission to view … nodes", with the count |
| View the data a staged change would delete, as counts of nodes, values and peers | INFP-719; D1 | Data deleted count, and "deletes N" on each migration |
| Recalculate the impact on demand | INFP-719; D1 | Recalculate beside "Impact calculated … ago" in the header |
| Impact calculation running, failed, out of date, or not matching the branch schema | D1 | One message for each state; Apply is unavailable while the impact runs, fails or does not match |
| Apply or discard a staged change, with the schema permission | INFP-719; D1 | Discard and Apply to branch, each with a confirmation; without permission, a tooltip names it |
| View the schema the staged change would produce | D1 (`staged=true`) | Schema viewer, Staged view |
| View the schema changes of a branch in order, growing with each load | INFP-719; B | Schema changes list: staged, failed loads, applied, newest first |
| View each application of a schema change, rebases included, with its migrations, statuses and errors | INFP-719 (recommendation); B | Runs on this branch section |
| Failed loads keep their error, have no version, and stay listed | B | Failed loads group, red chip with no version |
| A schema change that needs no migration is stored | B | "No change to data" on the row, no migration in its run |
| Loads made before the upgrade are combined into one schema change | B | "Loads made before the upgrade are combined here. Their order is not known." |
| View the revision of main and of each branch, and a pending staged change | INFP-719; B | "Revision 00030" above the list, the staged row, and two rows on the branch Details tab |
| Progress of an apply per migration, and nodes processed inside a migration | INFP-719 (must and nice to have); C1; C2 | Applying state: migrations ended out of the total, nodes migrated per migration, View the task |
| In the proposed change, view the schema changes the merge replays on main, in order | INFP-719; journey 4.1 | Proposed change, Schema changes: each row shows the version it gets on main |
| A failed merge rolls back completely, and the reviewer views the error | F2 | "Proposed change: merge rolled back" screen |
## Added in rev 8

Each one is in the investigation, in a project that is not optional, unless noted.

| Requirement | Source | Where in rev 8 |
|---|---|---|
| A staged change blocks merging the branch, and blocks direct loads and dropdown or enum changes on it, unless the action is forced | D1 | Proposed change: "The merge is blocked while a schema change is staged"; the staged row is "Staged, blocks the merge"; on the branch, the fact "Blocks merging and loading on this branch" |
| A failed apply keeps the change staged, with the error and the impact recalculated at apply | D1 | Staged change knob "apply failed": "The apply failed, so nothing changed on the branch" |
| The impact lists the checks that ran, including the ones that passed | D1 | Would fail section: "9 checks on the changed fields: 4 would fail, 5 pass", and the passing checks on request |
| Roll back a merge whose task stopped, with the Merge branch permission, as a task | INFP-719 (release the block without OpsMill); G1 | Screen "Proposed change: merge stopped": Roll back the merge, a confirmation, then "Rolling back the merge" |
| Progress of a merge, counted from its applications | INFP-719; B; C1 | Screen "Proposed change: merging": schema changes applied on main out of the total, and each row Applied, Running or Waiting |
| Progress of a direct load; a running schema change has no version | INFP-719; B; C1; C2 | Knob "a direct load is running": a Running group, and the change's progress per migration and per node |
| A run lists the operations it left out, with the reason | B | Run 2 of 00028: one operation removed at rebase because the conflict was resolved for main |
| A schema change skipped at merge leaves main an application only, with the branch name and the skipped operations | B | Main: group "Skipped at merge" |
| A migration that did not start because the load failed is `cancelled` | B | Run of the failed load `infradevice_asset_tag_kind_update` |

## Still partly covered or not covered

- **What a rebase will do, in the proposed change.** Optional project E. The "Merge into
  main" checks (Passes, Would fail, Not checked) also need E: without it, the proposed
  change checks the branch's data only (investigation, F2).
- **Progress of a rebase.** Each change's Runs section shows a running run, as for a direct
  load. No view sums up a whole rebase.
- **Forcing an action while a change is staged.** The API accepts `force` (D1); rev 8 does
  not offer it in the UI.
- **Permission on main.** Staging, applying and discarding on main also need
  `EDIT_DEFAULT_BRANCH`; the tooltip names only the Manage schema permission.
- **Schema changes from dropdown or enum changes** (B). Stored like loads; the mock data has
  none.
- **Rolling back with `force`** when the merge lock is missing needs `SUPER_ADMIN` (G1). Not
  shown.


## Out of scope, by decision or by the sources

- Resuming a stopped merge from the failed step, and changing data on main while it is
  stopped (INFP-719 must have): the investigation rolls back a failed merge completely, and
  the owner followed it on 2026-11-16.
- The revision as the name of the last migration with a schema hash (INFP-719): the
  investigation uses the version number, and the owner followed it.
- Data changes kept in their place between loads (journey 2.4, 3.1, 4.2): the investigation
  merges them as one set.
- Staging from the UI, and the CLI commands `infrahubctl schema view` and
  `infrahubctl schema load --stage` (investigation, out of scope).
- Exporting and importing migrations through Git (journey phase 6; investigation, out of
  scope).
- The list of objects and links a load deleted: the investigation stores counts only (nodes,
  attribute values and peers, plus the profile and template values that a unique or
  read-only change deletes), and the report in the load response stays in
  [IFC-3204](https://opsmill.atlassian.net/browse/IFC-3204). Links removed by a change of a
  relationship's peer are not counted, because that change runs a check, not a migration
  (INFP-719, open question 4).
- Merging or cancelling stored schema changes, several staged changes on one branch, and an
  estimated duration for an apply (INFP-719, not needed).
