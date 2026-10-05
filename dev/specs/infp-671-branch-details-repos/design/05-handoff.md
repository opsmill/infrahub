# Branch details: repositories and tasks — design handoff

Published page: https://claude.ai/artifact/REc7PuP1rDKRarH9G9V3wX (private until shared from its Share menu)

Design branch (backup, no PR): `ple-design-branch-details-repos`. Live prototype on that branch:
`/_proto/branch-details?dj.variant=object&dj.rev=6`.

## 1. What and why

> Redo the branch details page to also include the git repo changes: list the repos and display
> tasks related to repos. There are already tasks related to the branch, branch action buttons and
> branch details information.

Someone merged a branch from the branch page while a generator had failed on it, and the artifacts
came out stale. Today the only way to catch that is to open each repository page and then the
Tasks page, one by one. People merge from the branch page without a proposed change, so the
proposed change's checks never run.

## 2. The proposal: Object layout, rev 6

The branch details page uses the same layers, cards and colours as the object details page:

- **Header:** branch name, copy button, status badge, description, Refresh. Then the tabs.
- **Details card:** today's attribute grid, unchanged.
- **Git repositories card:** one row per repository, with name, Read-only tag, Git state
  (`sync_status`) and commit. Failing repositories sort first. It paginates at 10 rows, and the
  table keeps its height between pages.
  - **Import error band** under the table: the repository name, then the raw last error line of
    its import task in monospace, with "View task log →" to the task page. After 3 bands, the
    rest collapse into "N more repositories with errors" with a Show all button.
  - **Remote unreachable band** (`operational_status` error-cred, error-connection or error):
    amber, "Infrahub can't fetch new commits, so the commit shown may be out of date", and an
    "Open repository" link.
  - **Empty states:** no Git counterpart (Sync with Git off), no permission on repositories, and
    loading.
- **Branch actions:** today's inline buttons below the repositories: Merge, Propose change,
  Rebase, Validate, Delete. **Merge is not gated.**
- **Tasks card:** branch and repository tasks in one paginated table (Title, State, Workflow,
  Related, Updated). A failed count sits in the header, next to "Open in Tasks". Each title links
  to that task's details page, where the logs are. It has loading, empty and "results didn't load"
  states.

Screenshots (`shots/`):

| State | File |
|---|---|
| Import error + failed generator (worst case) | `object-incident.png` |
| Import error only | `object-import-error.png` |
| Failed generator only | `object-generator-failed.png` |
| Remote unreachable | `object-unreachable.png` |
| Import and generators running | `object-running.png` |
| 40 repositories, 5 import errors (both tables paginate) | `object-many-errors.png` |
| Task query failed | `object-tasks-unknown.png` |
| Everything passed | `object-all-clear.png` |
| No Git counterpart | `object-no-repos.png` |
| Loading | `object-loading.png` |
| No permission on repositories | `object-denied.png` |
| Today's page (baseline) | `current.png` |

## 3. What we rejected, and why

- **Checkpoint** (phase 2: repos inline, Merge opens a confirmation dialog). Evidence the user has
  to click to see is evidence they skip. The dialog also duplicated what the page already showed.
- **Readiness rail** (phase 2, refined as **Consistent**, rev 2): a sticky right rail owning the
  verdict and Merge, with the actions in a header menu. It works, but it breaks away from every
  other detail page. The summary also read as a duplicate of the Tasks table (round 1 feedback).
- **Repositories tab** (phase 2): the evidence gets its own tab, so it's one click away from where
  people decide to merge, the same failure as today.
- **Legacy** (rev 2): today's page shape with the repositories card and a merge readiness card.
  It's the smallest change, but it keeps the inconsistent layers and card styles that the Object
  layout fixes. Its round-1 note (Merge inside the card) was addressed and then superseded by the
  "merges aren't blocked" decision.

## 4. Decisions

The full log is in `03-decisions.md`. These are the ones reviewers will want to argue with:

| Decision | Reason |
|---|---|
| **Merge isn't gated** (round 6, owner). Import errors, failed generators and running tasks show on the page but don't block or warn on the button. | "Merges aren't blocked": the backend doesn't block them (INFP-670 has no backend gate), and a UI-only gate protects nobody who uses the API, SDK or CI. **This reverses brief decisions #1 and #3.** See open question 1. |
| Only data the backend returns today (round 5). No Upstream column, "N behind" or Last import. | No such fields exist. Upstream waits on IFC-3146, IFC-3147 and IFC-3154. Last import has no ticket, and IFC-3104 rules out `updated_at`. |
| Import errors show the raw last error log line. | `TaskError` (message, remediation) is only filled in for webhook tasks. Better text is IFC-3034. |
| `operational_status` errors warn in their own amber band. | The field exists and nothing shows it. The shown commit may be stale when the remote can't be reached. |
| Tasks aren't expandable: the title links to `/tasks/<id>` (round 6). | The task page already shows the logs, so a second log viewer isn't needed. |
| Inline buttons instead of an Actions menu (round 6). | They match today's page, and the owner asked for them. |
| Tables paginate at 10 rows with a fixed height. | 40 repositories or 55 tasks must not push the actions off screen. The pattern comes from IFC-3130's branch list. |

## 5. Open questions

1. **With Merge ungated, is the incident covered?** The brief's headline was "a warning names the
   failure before the merge goes through". Rev 6 makes failures visible just above the Merge
   button, but doesn't stop a click past them. Is visibility enough, or does this wait for
   INFP-670's backend gate? Decide with the INFP-670 owner.
2. **Does this card extend IFC-3200's Git repositories card, or replace it?** IFC-3200 is building
   the same columns (it's in progress). The error bands and pagination should land in that card,
   not in a second one.
3. **Which tasks does the table show?** The prototype shows repository imports, generators,
   artifacts, validate and rebase. Today's accordion shows only validate, merge and rebase. Should
   it be every task on the branch (`InfrahubTask(branch)`, server-paginated), or a workflow
   allow-list?
4. **Read-only repositories** are included, with a Read-only tag. Confirm.
5. **No named person yet** (brief). Before this ships, put rev 6 in front of whoever merged in the
   incident.

## 6. System gaps (work this design creates)

- **Shared table pagination:** `TablePagination` comes from IFC-3130 and isn't on INFP-671 or
  `stable`. Land it first, or copy it with the feature.
- **Latest import task per repository:** there's no query that returns it with its last error log
  line. Today that's `InfrahubTask(branch, related_node__ids, workflow, log_limit)` plus picking
  the latest in the frontend. A backend field (`last_import_task` on the repository) would be
  cleaner.
- **Structured import errors:** only raw log lines exist (IFC-3034).
- **Upstream head, "N behind", last import time:** IFC-3146, IFC-3147 and IFC-3154, plus a
  ticket that doesn't exist yet for last import.
- **Workflow display names:** there's no map from workflow id to a short label (Import,
  Generator, Artifacts, Validate, Rebase). The prototype hardcodes it.
- **The "Run all generators" parent flow** (`generator-definition-run`) is tagged with the
  branch only, so it can't be placed under a repository. It shows as a branch task ("This
  branch"). Its children are tagged with the definition, and reach the repository through
  `GeneratorDefinition.repository`.
- **`CopyToClipboardButton` has no accessible name** (found in review, shared component).
- **Dark mode:** the design branch has no theme support, so the prototype was never reviewed in
  dark mode. The implementation base (`cross-branch-repo-status-infp-671`) does have the theme
  (`frontend/packages/ui/src/theme`, `styles/theme.css`): use its tokens and check both themes.

## 7. How it got here

Every revision stays live on the design branch:

| Direction | Revisions |
|---|---|
| Current (baseline) | `?dj.variant=current&dj.rev=1` |
| Legacy | `?dj.variant=legacy&dj.rev=1`, `&dj.rev=2` |
| Consistent | `?dj.variant=consistent&dj.rev=1`, `&dj.rev=2` |
| Object layout | `?dj.variant=object&dj.rev=1` … `&dj.rev=6` |

Reasoning over time: `git log -p ple-design-branch-details-repos -- .design/branch-details-repos/`.
Code over time: `git diff <sha1>..<sha2> -- frontend/app/src/pages/_proto/`.

Files: `00-brief.md`, `01-system.md`, `02-directions.md`, `03-decisions.md`, `04-review.md`
(the gate is clean), and `shots/`.

---

## Lift sheet: from `revs/rev-06/` to production

Base the implementation branch on `cross-branch-repo-status-infp-671`. Copy the code; never
cherry-pick from the design branch. None of `_proto/`, the `designJam()` vite plugin or the
router block goes to production.

| Prototype file | Goes to | Notes |
|---|---|---|
| `root.tsx` (Object branch of the header) | `src/pages/branches/details.tsx` | Object-page header: name, `CopyToClipboardButton`, `BranchStatusBadge`, description, `RefreshButton`. Keep the real `BranchWorkingNotice`. Tabs + body `Card className="to-neutral-50"` as in `ObjectDetailsBody`. |
| `v-object.tsx` | The branch Details tab (`src/pages/branches/…` outlet) | Column: `BranchAttributes` (real) → repositories card → branch actions → tasks card. Replace `fakeMerge` and the toasts with the real `BranchMergeButton`, `BranchRebaseButton`, validate and delete actions. |
| `git-repositories-card.tsx` | `src/entities/repository/ui/branch-repositories/` (or IFC-3200's card, see open question 2) | Keep the row, the Git state pill, the bands and the pagination. Drop the non-object header variant. |
| `data.ts`: `GIT_STATE`, `OPERATIONAL_ERROR`, `rank()` | `src/entities/repository/domain/model` and `domain/rules` | Pure functions: unit test them. `rank` should become server-side ordering if the repository query supports it. |
| `data.ts`: scenarios (`buildData`) | Test fixtures for the card and tasks table | One fixture per scenario in the screenshot table. They're the test matrix. |
| `tasks-table.tsx` | `src/entities/tasks/ui/branch-tasks-table.tsx` | The link goes to `constructPath(\`/tasks/${id}\`)`. Server-side pagination (`limit`/`offset`, `count`) instead of slicing. |
| `table-pagination.tsx` | Nothing; use IFC-3130's `shared/components/table/table-pagination.tsx` | The copy exists only because IFC-3130 isn't on this branch. |
| `shared.tsx` (`Attributes`) | Nothing; use the real `BranchAttributes` | A replica for the prototype. |
| `real-task-ids.ts`, `locate.ts`, `merge-rail.tsx`, `branch-actions-menu.tsx`, `controls.css`, `v-legacy.tsx`, `v-consistent.tsx` | Nothing | Prototype-only. |

### Queries

1. **Repositories on the branch:** `CoreGenericRepository` on the branch with `name`, `__typename`
   (Read-only), `commit`, `sync_status`, `operational_status`. Paginated.
   _(Note 2026-10-05: this lists read-write and read-only repositories together, because
   `CoreGenericRepository` is the generic both kinds inherit from. A branch created with Sync with
   Git off tracks only read-only repositories, so on that branch the implementation sends a separate
   query, `CoreReadOnlyRepository` with the same fields, order and pagination. The health query that
   feeds the bands and polling has the same read-only variant. See `research.md` D1 and
   `data-model.md` `getRepositoryListKind`.)_
2. **Latest import task per failing repository:** `InfrahubTask(branch, related_node__ids: [repo],
   workflow: [import workflows], limit: 1, log_limit: N)`. The last error-severity log line is the
   band's text.
3. **Tasks table:** `InfrahubTask(branch, limit, offset)`, with `count` for pagination and
   `related_nodes` for the Related column. Resolve repository names from query 1.
4. **Refresh:** invalidates 1–3. (The IFC-3199 header indicator, which polls repository counts,
   is on its own branch, `ple-git-status-header-ifc-3199`, not on the implementation base, so
   there are no shared query keys to reuse yet. Align them when both land.)

### Checks before pushing

`pnpm exec biome ci .`, `pnpm knip`, `pnpm exec betterer ci`, `pnpm test`. Component tests per
scenario fixture, an e2e test for "import error band links to the task page", and the pagination
boundary (exactly 10 and 11 repositories).
