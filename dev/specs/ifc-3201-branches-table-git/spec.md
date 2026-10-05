# Feature Specification: Repositories and Git state columns on the branches list

**Feature Branch**: `ple-branches-table-git-ifc-3201` (based on `ple-branch-details-repos-infp-671`, PR #10779, itself based on `cross-branch-repo-status-infp-671`)

**Created**: 2026-09-30

**Status**: Draft

**Jira**: [IFC-3201](https://opsmill.atlassian.net/browse/IFC-3201), under epic [IFC-3104](https://opsmill.atlassian.net/browse/IFC-3104) (Cross-branch repository status query), part of INFP-671 (Git repository sync visibility)

**Design**: Git sync visibility canvas, section 3 (linked from the ticket). Phase 1 research and the owner's checkpoint decisions: `research-brief.md` in this directory.

**Builds on**: `dev/specs/infp-671-branch-details-repos/` (PR #10779), which already answers "which Git repositories does this branch have, in what state, at which commit" for one branch and renders the Git state pill. This feature asks the same question for every branch in the list and keeps its answers: Git state is the repository's `sync_status` with the schema's own label and colour, a caller without repository permission is told so rather than shown a trimmed list, and no "last import" time is derived from attribute timestamps.

**Input**: User description: "Feature IFC-3201 — Repository, Git state and Commit columns on the branches table. Surface Git health one level up, in the branches list, so a broken branch is visible without opening it. Three new columns — Repository, Git state, Commit. A branch can link to several repositories: it renders as an ordinary table that repeats the branch across one row per repository. No summary cell, no stacking inside a cell. Branches not synced with Git need an explicit empty state, not a dash. Upstream and Last import are not in this ticket."

## Problem Statement

The branches list tells you a branch exists, whether it is open or merged, and who created it. It says nothing about the branch's Git repositories. When an import fails on one branch out of fifty, the only way to find it today is to open each branch (or each repository page) in turn. The branch details page (PR #10779) shows Git health for one branch once you are there; this feature puts the same signal one level up, in the list, so a failing repository is visible while scanning branches, without opening any of them.

A branch can have several repositories, and their states differ. The list keeps one row per branch and shows a branch's repositories the way the Proposed changes cell shows a many-valued relationship: the first repository, failed imports first, as a link, followed by a "+N more" link, counting the other repositories, that opens the branch. The Git state column shows the worst state among them with an n/N count, so a failing repository surfaces on its branch's row however many healthy ones the branch also has. The full list, with every commit, stays on the branch details page.

## Clarifications

### Session 2026-09-30

Decisions taken by the feature owner at the phase 1 checkpoint. They are binding for this run.

- Q: Which branch does this work build on, given that the repository data layer, Git state pill and test fixtures exist only on unmerged sibling PRs? → A: **Stack on PR #10779's branch** (`ple-branch-details-repos-infp-671`) and reuse its repository layer as-is. The pull request targets that branch. The Commit display component lives on PR #10658's branch; it is lifted byte-identical at the same path so the later merge is clean.
- Q: One row per branch × repository, or a stacked cell? → A: **One row per branch × repository**, repeating every branch cell (checkbox, name, status, proposed changes, actions) on each repository row. Selecting any row of a branch selects that branch once.
- Q: What does a branch with no repositories show? → A: **One row with an explicit text in the Repository cell**: "Not synced with Git" when the branch is not synced with Git, "No repositories" otherwise, in muted text (`text-foreground-muted`, per the review session below). Git state and Commit stay blank (no dash). A branch that is not synced with Git but still has read-only repositories lists them normally.
- Q: How is the commit rendered? → A: **Short 7-character hash in a monospace face, the full hash available on hover, with a copy button on every row.**

Clarifications settled from the research brief and the base branch (PR #10779), without a user question:

- Q: What exactly does the Repository cell contain, and where does its link go? → A: **The same as the branch details page's repository row**: the repository name linking to the repository's page opened on that branch, and a "Read-only" marker for read-only repositories.
- Q: In which order do a branch's repository rows appear? → A: **The branch details page's order**: failed imports first, then unreachable remotes, then by name. The ordering rule is reused, not re-implemented.
- Q: Does the Git state cell also flag an unreachable remote (the repository's operational status), as the branch details row does? → A: **No.** The ticket scopes Git state to the import outcome (`sync_status`) only. Operational status stays on the branch details page.
- Q: Can the three new columns be hidden? → A: **No.** The branches list has no column picker today and this feature does not add one.
- Q: Are other screens affected? → A: **No.** The branches table is rendered by the branches page only.

### Session 2026-09-30 (critique)

Decisions taken by the conductor on `critiques/critique-2026-09-30.md`. The owner reviews them at the phase 2 checkpoint.

- Q: Can SC-004 promise that no existing cell moves while repository data arrives (X1)? → A: **Horizontally, yes; vertically, no.** The three new columns get fixed-width tracks, so no column shifts sideways. Rows below a branch may move down when its repositories arrive.
- Q: Is the row multiplier from read-only repositories accepted (P1)? → A: **Yes.** A read-only repository appears on every branch, so with R read-only repositories every branch has at least R rows. This is the backend's row set.
- Q: Should the list keep the branch details order, even though an unreachable-remote change can reorder rows live (P2)? → A: **Keep it.** The anchor row of a branch may change when a repository's reachability changes; selection is keyed by branch and is unaffected.
- Q: How many loading indicators does a pending branch show (P3)? → A: **One, in the Repository cell.** Git state and Commit stay blank while pending.
- Q: How do keyboard and screen-reader users tell a branch's repeated rows apart (P4)? → A: **Only the first row's checkbox is in the tab order.** It is named "Select <branch>"; the other rows' checkboxes are named "Select <branch> (<repository name>)" and are skipped by Tab. (Widened in the review session to every repeated branch control.)
- Q: Where does the failure message go once the toast is suppressed (E3)? → A: **On the "Could not load repositories" text, as a tooltip** carrying the error message. (Extended in the review session: also as visually hidden text.)
- Q: Is an early next-page load caused by short pending rows acceptable (E9)? → A: **Yes**, recorded as an edge case.
- Q: Is there a bound on the requests and re-renders the columns cause (P6)? → A: **Yes, SC-007**: one branch's resolution re-renders that branch's rows only, and a window refocus issues at most one repository request per loaded branch.

### Session 2026-09-30 (review)

Corrections from the phase 4 review pass (`review-synthesis.md` in this directory, "Spec corrections implied"). They supersede the matching critique answers above.

- Q: Which colour do the state texts ("Not synced with Git", "No repositories", "No permission", "Could not load repositories") use? → A: **`text-foreground-muted`**. `text-subtle-muted` is under 4.5:1 contrast and is kept for decorative text, while these states are what the ticket delivers (FR-007, FR-012, FR-013).
- Q: Is a hover tooltip enough to carry the load error's message (E3)? → A: **No.** The message is also rendered as visually hidden text next to "Could not load repositories", so keyboard and screen-reader users reach it; the tooltip stays for pointer users (FR-013).
- Q: Which controls on a branch's repeated rows leave the tab order (P4)? → A: **Every repeated branch control**: the checkbox, the branch name link, the proposed-changes pill and the actions menu are tabbable on the anchor row only. The commit copy button stays tabbable on every row, because each row's commit differs (FR-008).
- Q: Should the repository name reveal a truncated name with the `Tooltip` component, like the branch name does? → A: **Not in this feature.** `RepositoryNameLink` keeps the native `title` it has on the branch details card. Aligning it with `Tooltip` is a follow-up.
- Q: How does the hook keep one branch's resolution from re-rendering the others (SC-007)? → A: **It calls the row rule once over all loaded branches and returns the rows grouped by branch id.** TanStack's structural sharing then pairs rows by branch, not by array index, so a branch growing from one pending row to N leaves every other branch's row objects untouched. No caches (research R13).
- Q: What does the branch details card show once the error toast is suppressed? → A: **Its failed state shows the server's error message**, so suppressing the toast loses no information on either page.

### Session 2026-10-01 (owner, after trying it on a dev stack)

The owner tried the one-row-per-repository list on a dev stack and reversed it. These answers supersede the matching 2026-09-30 answers above, which stay as history. Measurements and the single-request finding: research R14.

- Q: One row per branch × repository, or one row per branch? → A: **One row per branch.** With 24 branches × 16 repositories the fan-out rendered 279 rows, 280 checkboxes and about 15 000 DOM nodes and was visibly slow, while the 24 repository requests took 0.36 s in total: the cost is rendering, not fetching. The ticket's "one row per repository" assumed one or two repositories per branch. This reverses the 2026-09-30 fan-out answer and the critique answers that depend on it (P1 multiplier, P2 anchor change, P4 tab order).
- Q: What does the Repositories cell show? → A: **The first repository as a pill, then "+N more".** Repositories are ordered by the branch details rule (failed imports first, then unreachable remotes, then by name), the first one is a pill linking to the repository's page on the row's branch, and when there are more, "+N more" links to the branch details page, as the Proposed changes cell does.
- Q: What does the Git state cell show? → A: **A roll-up**: the Git state pill of the worst state (the first repository's, since failed imports rank first), followed by an `n/N` count of the repositories in that state when the branch has more than one, with a tooltip listing the count per state label (for example `Import Error: 1 · In Sync: 15`).
- Q: Is the Commit column kept? → A: **No, it is dropped.** The commit is shown in the repository pill's tooltip (7 characters) and on the branch details page. The copy control on commits goes with it.
- Q: How does selection work? → A: **The ordinary way**: one row per branch, so one checkbox per branch, named "Select <branch>". The anchor-row selection and the tab-order rules for repeated rows are gone with the repeated rows.

### Session 2026-10-01 (architecture review)

Owner decisions after the architecture review of the one-row-per-branch implementation. Binding contract: `rework-contract-a.md`; reasoning: research R15. These answers supersede the matching answers above (data source, ordering, per-branch denial and failure, shared cache), which stay as history.

- Q: Where does the list read repository data from? → A: **From the epic's `InfrahubRepositoryBranchStatus`, once per repository, pivoted to one summary per branch in the branches domain.** The per-branch `CoreGenericRepository` requests issued from inside the cells are gone. Why: the two cells owned and duplicated the data and its derivation (same query, same ranking); pure derivation lived in `.tsx`; the roll-up reused the details card's band ordering and showed an unreachable repository as "In Sync" above a real failure; and the per-branch query mirrored the backend's row-set rule on the client, which the epic's query exists to keep server-side.
- Q: In which order are a branch's repositories ranked? → A: **By Git state severity, `error-import` > `unknown` > `syncing` > `in-sync`, then by repository name (case-insensitive).** A value outside this list ranks with `unknown`. Operational status (remote reachability) no longer affects the order.
- Q: What does a permission denial do? → A: **It blanks the column for every row when the repository list is denied, or when every status read is denied.** The repository list reads both kinds in one query, so lacking view on either kind denies it. With the list readable, a repository whose status read is denied is left out silently; only when every status read is denied does every row's Repositories cell read "No permission" and every Git state cell is blank. A load failure of any repository's status likewise reads "Could not load repositories" on every row. The branch cells always render.
- Q: What do merged branches show, if the list filter shows them? → A: **"No repositories".** The status query excludes merged, deleting and global branches from its rows.
- Q: Is the cache still shared with the branch details page? → A: **No.** The list reads a different query; the details page keeps #10779's per-branch query.
- Q: How many requests does the list issue? → A: **1 + R** (one repository list, one status request per repository; 16 on the dev stack), independent of how many branch pages are loaded. The backend `repository_ids` follow-up collapses this to 2 without touching cells or rules.
- Q: What bounds a window refocus? → A: **A 60 s stale time on the status queries.** A refocus within 60 s of the last fetch issues no request; a status query polls every 10 s only while one of its rows is syncing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Spot a broken repository from the branches list (Priority: P1)

An operator opens the branches list and, without opening any branch, sees for every branch which Git repository comes first on it (a failed import if there is one) and the worst Git state among the branch's repositories.

**Why this priority**: This is the whole reason for the ticket. Everything else (the "+N more" link, the count, the empty states) exists to make this reading correct.

**Independent Test**: With one repository whose import failed on one branch, load the branches list and confirm that branch's row shows the failed repository's name and a Git state pill reading the failed state in the schema's colour, while other branches show their own states.

**Acceptance Scenarios**:

1. **Given** a branch with one repository that last imported successfully, **When** the operator views the branches list, **Then** that branch's row shows the repository's name as a link to the repository's page on that branch, and a Git state pill with the schema's label and colour for the successful state, with no count.
2. **Given** a branch with one repository that failed to import, **When** the operator views the list, **Then** the Git state pill reads the failed state in the schema's colour for it, and hovering the pill shows the state's description.
3. **Given** a branch with a repository, **When** the operator hovers the repository's name, **Then** a tooltip shows the repository's Git state label and the first 7 characters of the commit that branch has imported, and says "read-only" for a read-only repository.
4. **Given** the list is loading a branch's repository data, **When** the branch row is already visible, **Then** the branch's own cells (name, status, proposed changes, actions) render immediately, the Repositories cell shows one loading indicator until the data arrives, and the Git state cell stays blank until then.

---

### User Story 2 - A branch with several repositories reads as one row with its worst state (Priority: P2)

A branch linked to sixteen repositories still appears once in the list. Its Repositories cell names the repository that needs attention first and offers the rest through "+15 more", and its Git state cell tells how many repositories share the worst state.

**Why this priority**: Real deployments link many repositories to every branch (each read-only repository appears on every branch). One row per repository made the list unusable at that scale (research R14); a roll-up keeps the failing signal while the list stays one row per branch.

**Independent Test**: With a branch linked to three repositories of which one failed to import, load the list and confirm one row for that branch, whose Repositories cell shows the failed repository followed by "+2 more", and whose Git state cell shows the failed state followed by "1/3".

**Acceptance Scenarios**:

1. **Given** a branch with N ≥ 2 repositories, **When** the list renders, **Then** the branch appears on exactly one row, its Repositories cell shows the first repository followed by "+N−1 more", and "+N−1 more" links to the branch's details page.
2. **Given** a branch with three repositories of which one failed to import, **When** its row renders, **Then** the Repositories cell shows the failed repository, the Git state cell shows the failed state's pill followed by "1/3", and hovering the pill and count lists the count per state label, for example "Import Error: 1 · In Sync: 2".
3. **Given** a branch with several repositories, **When** the operator ticks its checkbox, **Then** the toolbar reports 1 selected and the bulk delete dialog lists that branch once, as it does today.
4. **Given** the list is scrolled to load more branches, **When** the next page arrives, **Then** the new branches append one row each, and the number of branches per page is unchanged from today.
5. **Given** a branch with several repositories, **When** its row renders, **Then** the repository shown first follows the severity order (failed imports, then unknown, then syncing, then in sync, each by name), identically across reloads.

---

### User Story 3 - A branch with no repositories reads as deliberately empty (Priority: P3)

A branch that is not synced with Git, or that has no repositories at all, says so in words in its Repositories cell rather than with a dash, so the operator knows nothing is missing.

**Why this priority**: The ticket calls out that an empty state must not look broken. This story also covers the degraded states (no permission, load failure), which must never hide the branch itself.

**Independent Test**: With a branch that is not synced with Git and has no read-only repositories, load the list and confirm its Repositories cell reads "Not synced with Git" and its Git state cell is blank.

**Acceptance Scenarios**:

1. **Given** a branch not synced with Git and with no read-only repositories, **When** the list renders, **Then** its Repositories cell reads "Not synced with Git" and its Git state cell is blank.
2. **Given** a branch synced with Git but with no repositories registered, **When** the list renders, **Then** its Repositories cell reads "No repositories".
3. **Given** a branch not synced with Git that has read-only repositories, **When** the list renders, **Then** those repositories are shown like any other (first repository, "+N more", Git state roll-up).
4. **Given** the operator lacks permission to read any repository kind on every branch, **When** the list renders, **Then** every branch's cells render normally, every Repositories cell reads "No permission" in a muted style and every Git state cell is blank.
5. **Given** a repository's status fails to load, **When** the list renders, **Then** every branch's cells render normally, every Repositories cell reads "Could not load repositories" in a muted style, every Git state cell is blank, and no toast or page-level error appears.

---

### Edge Cases

- A repository whose Git state has no colour defined in the schema: the pill falls back to a neutral style and still shows the state's value (or its label if there is no value), as the branch details page's pill already does.
- A repository with no commit yet: its tooltip shows the Git state label only, without a commit part.
- A freshly created synced branch reports the default branch's fork-point commit; it is displayed as returned, not treated as empty.
- "Worst" is the first repository in severity order (`error-import` > `unknown` > `syncing` > `in-sync`, then by name). An unreachable remote whose last import succeeded ranks as `in-sync`, so it never hides a failed import elsewhere (superseded 2026-10-01: the branch details band ordering is no longer used). A state value outside the list ranks with `unknown`.
- A merged branch, if the list filter shows it, has no status rows and reads "No repositories".
- The repository list needs view permission on both repository kinds; without it, "No permission" reads on every row. With the list readable, each status read needs view on all branches: a denied one is left out silently, and "No permission" reads on every row only when every status read is denied.
- Several repositories in the worst state: the count `n/N` counts every repository whose state value equals the shown one.
- A branch whose repositories change from loading to loaded: the row keeps its position; the two new columns have fixed widths, so no column shifts sideways. The row may grow taller if the cell wraps.
- A repository that is currently syncing: its status query refreshes every 10 s, the cadence the branch details page already uses, and stops when the sync settles.
- A branch page loaded by scrolling: it is summarized from the status rows already loaded, with no new status request.
- A branch created outside this page (Git import, another user): it may read "No repositories" until the 60 s status stale time passes or the list is reloaded. Branches created, deleted, merged or rebased from this UI refresh the status cache immediately. Accepted: re-reading every repository's status on every new branch name would turn scrolling and search into R requests each.
- The default branch: it stays first in the list; its repository link carries `branch=<default name>` like every other row (the base's `getBranchQsp`).
- Existing filters (status, name, created-by, dates) continue to filter by branch; no filter or sort is offered on the two new columns.
- Column count changes: the table's column layout accommodates the two new columns without misplacing the existing ones.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The branches list MUST show two additional columns, in this order after "Proposed changes": "Repositories", "Git state".
- **FR-002**: The list MUST keep one row per branch. Repository data MUST NOT add rows.
- **FR-003**: The set of repositories counted and shown for a branch MUST be what the backend returns for that branch: the rows of `InfrahubRepositoryBranchStatus` whose branch name matches, one query per repository (read/write repositories list only branches synced with Git, read-only repositories list every branch; merged, deleting and global branches are excluded). The list MUST NOT re-derive that set on the client from the branch's sync flag or status.
- **FR-004**: For a branch with N ≥ 1 repositories, the Repositories cell MUST show the first repository (FR-005) as a pill linking to that repository's page opened on the row's branch, the default branch included. Hovering it MUST show the repository's Git state label and the first 7 characters of its commit (omitted when there is no commit), and "read-only" for a read-only repository. When N > 1 it MUST be followed by a "+N−1 more" link to the branch's details page.
- **FR-005**: Repositories MUST be ordered by Git state severity, `error-import` > `unknown` > `syncing` > `in-sync`, each group sorted by repository name (case-insensitive). A state value outside this list ranks with `unknown`. Operational status (remote reachability) MUST NOT affect the order (superseded 2026-10-01: the branch details band ordering).
- **FR-006**: For a branch with N ≥ 1 repositories, the Git state cell MUST show the first repository's `sync_status` as resolved on that branch (the worst state), rendered with the label, colour and description defined in the schema. When no colour is defined, the pill MUST fall back to a neutral style and still show the state's value or label, identically to the branch details page's pill. When N > 1, the pill MUST be followed by an `n/N` count, where n is the number of repositories whose state value equals the shown one, and hovering them MUST list the count per state label.
- **FR-007**: For a branch that returns zero repositories, the Repositories cell MUST read "Not synced with Git" when the branch is not synced with Git and "No repositories" otherwise, in muted text (`text-foreground-muted`); the Git state cell MUST be blank.
- **FR-008**: Selection MUST stay per row, which is per branch, as today. The row checkbox MUST be named "Select <branch>".
- **FR-009**: Shift-click range selection MUST continue to work unchanged.
- **FR-010**: Pagination MUST continue to count branches per page; a page with N branches renders N rows.
- **FR-011**: Repository data MUST be fetched by the page, not by the cells: one repository-list request on the default branch, then one `InfrahubRepositoryBranchStatus` request per repository (1 + R requests), independent of how many branch pages are loaded. The fetch starts after the branch rows are shown: branch cells render immediately, and every Repositories cell shows one loading indicator until the repository list and every status request have arrived; the Git state cell stays blank until then. Cells receive the per-branch summary as data and own no fetch.
- **FR-012**: When the repository list is denied (the operator lacks view permission on either repository kind) or every status read is denied (a single denied status read leaves that repository out silently), every branch MUST render with its branch cells intact, a muted (`text-foreground-muted`) "No permission" text in every Repositories cell and a blank Git state cell. No page-level error is shown.
- **FR-013**: When any status request fails for another reason and holds no earlier data, every branch MUST render a muted (`text-foreground-muted`) "Could not load repositories" text in the Repositories cell and a blank Git state cell, without toasts or page-level errors. The load error's message MUST stay reachable: it is shown as a tooltip on that text for pointer users and rendered as visually hidden text alongside it for keyboard and screen-reader users. A failed background refetch keeps the last loaded rows.
- **FR-014**: A status query with a row whose `sync_status` is `syncing` MUST refresh every 10 s, the cadence already used by the branch details page, and stop when the sync settles. Status queries MUST have a 60 s stale time, so a window refocus within 60 s of the last fetch issues no request.
- **FR-015**: The two new columns MUST NOT be filterable or sortable in this feature. Existing filters and the default ordering (default branch first, then by name) are unchanged.
- **FR-016**: The list MUST NOT show a Commit column, an upstream commit, a "behind by N" figure, a last-import time, or the repository's operational (remote reachability) status. The commit appears only in the repository pill's tooltip and on the branch details page.
- **FR-017**: The two new columns MUST always be shown; no column-hiding control is added to the branches list.

### Key Entities *(include if feature involves data)*

- **Branch row**: one line of the table per branch, as today. Carries the branch's existing attributes and, once loaded, the branch's repositories in ranked order.
- **Repository on a branch**: a Git repository as seen from one branch: name, kind (read/write or read-only), Git state (`sync_status`: value, label, colour, description) and imported commit. Built page-side from one `InfrahubRepositoryBranchStatus` row and the repository list (`BranchRepositoryState`, data-model.md).
- **Git state**: the outcome of the repository's last import on that branch, as a schema-defined dropdown value. Distinct from the branch's own lifecycle status. The list shows the first-ranked repository's Git state, with a count per state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can identify every branch with a failed repository import by scanning the branches list, with zero branch or repository pages opened.
- **SC-002**: Every branch appears on exactly one row; a branch with no repositories shows the explicit empty text and never a dash.
- **SC-003**: Selecting a branch and running bulk delete acts on exactly the selected branches; the selection count matches, as today.
- **SC-004**: Branch name, status and proposed-change cells are rendered before any repository data resolves; the new cells fill in afterwards without shifting any column horizontally.
- **SC-005**: A permission or load failure on repository data leaves every branch's own cells (name, status, proposed changes, actions) fully rendered.
- **SC-006**: Every state in this spec (one repository, several with a count, loading, empty for both texts, denied, failed, no colour, no commit, severity order) has an automated test; the frontend lint, unused-code, type-regression and unit test gates pass.
- **SC-007**: 1 + R requests per page load, no new status requests on scroll, no re-fetch within 60 s of refocus.

## Assumptions

- The branch details work (PR #10779) is the base and merges before this feature. Its repository-list hook, Git state pill and test fixtures are reused unchanged; its per-branch query stays the details page's and is no longer called by the list (superseded 2026-10-01, architecture review).
- The status read is lifted from PR #10658 (`InfrahubRepositoryBranchStatus` API, model and use case); its hook is not, because it forces the current branch. The list adds a query-options factory and a `branchStatus` query key instead (plan Complexity Tracking).
- Repository data is fetched with 1 + R requests: the repository list once, then one status request per repository (`limit: 500`) on the default branch, taken from the branches provider by `is_default`, never by name. No query is shared with the branch details page: the table reads the repository list with one 500-row page and the status pages, while the card pages its own list. The backend `repository_ids` follow-up collapses this to 2 requests (research R15).
- The repositories per branch follow the backend: a read/write repository appears only on branches synced with Git; a read-only repository appears on every branch. The list uses the branch's sync flag only to choose the empty-state wording.
- A read-only repository appears on every branch, so with R read-only repositories every branch counts at least R repositories in its "+N more" and `n/N` figures.
- Merged and deleting branches, if shown by the current list filters, read "No repositories": the status query excludes them.
- The status query needs repository view permission on all branches; without it the whole column reads "No permission".
- The commit shown for a fresh synced branch is the fork-point commit, as the backend resolves it.
- The epic spec (`dev/specs/infp-671-cross-branch-repo-status/spec.md`) lists "extra columns on the global branches view" as out of scope for the backend query work; this ticket is the frontend follow-up that supersedes that line, reads the epic's query and adds no backend change.
- The branches table is rendered only by the branches page, so no other screen changes.
- When the backend truncates a branch's repository list, the list counts only the returned repositories, with no extra marker.
- Out of scope: "Upstream" and "Last import" columns (IFC-3146, IFC-3147), a Commit column, the repository's operational status (unreachable remote), filters or sorting on the new columns, column hiding, any backend change, the branch-details page itself, and resolving the visual similarity between the branch "Status" pill and the "Git state" pill beyond keeping them separated by the "Proposed changes" and "Repositories" columns and using different pill shapes.
