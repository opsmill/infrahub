# Feature Specification: Repository, Git state and Commit columns on the branches table

**Feature Branch**: `ple-branches-table-git-ifc-3201` (based on `ple-branch-details-repos-infp-671`, PR #10779, itself based on `cross-branch-repo-status-infp-671`)

**Created**: 2026-09-30

**Status**: Draft

**Jira**: [IFC-3201](https://opsmill.atlassian.net/browse/IFC-3201), under epic [IFC-3104](https://opsmill.atlassian.net/browse/IFC-3104) (Cross-branch repository status query), part of INFP-671 (Git repository sync visibility)

**Design**: Git sync visibility canvas, section 3 (linked from the ticket). Phase 1 research and the owner's checkpoint decisions: `research-brief.md` in this directory.

**Builds on**: `dev/specs/infp-671-branch-details-repos/` (PR #10779), which already answers "which Git repositories does this branch have, in what state, at which commit" for one branch and renders the Git state pill. This feature asks the same question for every branch in the list and keeps its answers: Git state is the repository's `sync_status` with the schema's own label and colour, a caller without repository permission is told so rather than shown a trimmed list, and no "last import" time is derived from attribute timestamps.

**Input**: User description: "Feature IFC-3201 — Repository, Git state and Commit columns on the branches table. Surface Git health one level up, in the branches list, so a broken branch is visible without opening it. Three new columns — Repository, Git state, Commit. A branch can link to several repositories: it renders as an ordinary table that repeats the branch across one row per repository. No summary cell, no stacking inside a cell. Branches not synced with Git need an explicit empty state, not a dash. Upstream and Last import are not in this ticket."

## Problem Statement

The branches list tells you a branch exists, whether it is open or merged, and who created it. It says nothing about the branch's Git repositories. When an import fails on one branch out of fifty, the only way to find it today is to open each branch (or each repository page) in turn. The branch details page (PR #10779) shows Git health for one branch once you are there; this feature puts the same signal one level up, in the list, so a failing repository is visible while scanning branches, without opening any of them.

A branch can have several repositories, and their states differ. Rather than summarise them into one cell, the list shows one row per branch and repository, the way every other table in the app shows one thing per row. A failing repository is therefore its own row, not a detail hidden inside a branch row.

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

Corrections from the phase 5 review pass (`review-synthesis.md`, "Spec corrections implied"). They supersede the matching critique answers above.

- Q: Which colour do the state texts ("Not synced with Git", "No repositories", "No permission", "Could not load repositories") use? → A: **`text-foreground-muted`**. `text-subtle-muted` is under 4.5:1 contrast and is kept for decorative text, while these states are what the ticket delivers (FR-007, FR-012, FR-013).
- Q: Is a hover tooltip enough to carry the load error's message (E3)? → A: **No.** The message is also rendered as visually hidden text next to "Could not load repositories", so keyboard and screen-reader users reach it; the tooltip stays for pointer users (FR-013).
- Q: Which controls on a branch's repeated rows leave the tab order (P4)? → A: **Every repeated branch control**: the checkbox, the branch name link, the proposed-changes pill and the actions menu are tabbable on the anchor row only. The commit copy button stays tabbable on every row, because each row's commit differs (FR-008).
- Q: Should the repository name reveal a truncated name with the `Tooltip` component, like the branch name does? → A: **Not in this feature.** `RepositoryNameLink` keeps the native `title` it has on the branch details card. Aligning it with `Tooltip` is a follow-up.
- Q: How does the hook keep one branch's resolution from re-rendering the others (SC-007)? → A: **It calls the row rule once over all loaded branches and returns the rows grouped by branch id.** TanStack's structural sharing then pairs rows by branch, not by array index, so a branch growing from one pending row to N leaves every other branch's row objects untouched. No caches (research R13).
- Q: What does the branch details card show once the error toast is suppressed? → A: **Its failed state shows the server's error message**, so suppressing the toast loses no information on either page.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Spot a broken repository from the branches list (Priority: P1)

An operator opens the branches list and, without opening any branch, sees for every branch which Git repositories it has, whether each repository's last import on that branch succeeded, and which commit that branch has imported.

**Why this priority**: This is the whole reason for the ticket. Everything else (row fan-out, empty states) exists to make this reading correct.

**Independent Test**: With one repository whose import failed on one branch, load the branches list and confirm that branch's row shows the repository's name, a Git state pill reading the failed state in the schema's colour, and the imported commit, while other branches show their own states.

**Acceptance Scenarios**:

1. **Given** a branch whose repository last imported successfully, **When** the operator views the branches list, **Then** that branch's row shows the repository's name, a Git state pill with the schema's label and colour for the successful state, and the first 7 characters of the imported commit.
2. **Given** a branch whose repository failed to import, **When** the operator views the list, **Then** the Git state pill reads the failed state in the schema's colour for it, and hovering the pill shows the state's description.
3. **Given** a repository row with a commit, **When** the operator hovers the commit, **Then** the full hash is shown; **When** they press the copy control, **Then** the full hash is copied and the control confirms it.
4. **Given** the list is loading a branch's repository data, **When** the branch row is already visible, **Then** the branch's own cells (name, status, proposed changes, actions) render immediately, the Repository cell shows a loading indicator until the data arrives, and the Git state and Commit cells stay blank until then.

---

### User Story 2 - A branch with several repositories reads as several rows (Priority: P2)

A branch linked to three repositories appears three times in the list, once per repository, each row carrying that repository's Git state and commit. Bulk actions still operate on branches, not rows.

**Why this priority**: Multiple repositories are common in real deployments, and the ticket forbids summarising them. Getting selection and bulk actions right is what keeps the fan-out from breaking existing behaviour.

**Independent Test**: With a branch linked to three repositories, load the list and confirm three consecutive rows for that branch; tick one of them and confirm the toolbar reports one selected branch and the bulk delete dialog lists the branch once.

**Acceptance Scenarios**:

1. **Given** a branch with N repositories, **When** the list renders, **Then** the branch appears on N consecutive rows, each showing the same branch name, status and proposed changes and a different repository, Git state and commit.
2. **Given** a branch shown on several rows, **When** the operator ticks the checkbox on any of those rows, **Then** every row of that branch shows as selected, the toolbar reports 1 selected, and the bulk delete dialog lists that branch once.
3. **Given** two branches with several repositories each, **When** the operator uses shift-click to select a range covering both, **Then** the toolbar reports 2 selected.
4. **Given** the list is scrolled to load more branches, **When** the next page arrives, **Then** the new branches append with their repository rows, and the number of branches per page is unchanged from today.
5. **Given** a branch with several repositories of which one failed to import, **When** its rows render, **Then** the failed repository is the branch's first row and the others follow in the branch details page's order (unreachable remotes next, then by name), identically across reloads.

---

### User Story 3 - A branch with no repositories reads as deliberately empty (Priority: P3)

A branch that is not synced with Git, or that has no repositories at all, still appears exactly once, and its Repository cell says so in words rather than with a dash, so the operator knows nothing is missing.

**Why this priority**: The ticket calls out that an empty state must not look broken. This story also covers the degraded states (no permission, load failure), which must never hide the branch itself.

**Independent Test**: With a branch that is not synced with Git and has no read-only repositories, load the list and confirm one row whose Repository cell reads "Not synced with Git" and whose Git state and Commit cells are blank.

**Acceptance Scenarios**:

1. **Given** a branch not synced with Git and with no read-only repositories, **When** the list renders, **Then** the branch has exactly one row, its Repository cell reads "Not synced with Git", and its Git state and Commit cells are blank.
2. **Given** a branch synced with Git but with no repositories registered, **When** the list renders, **Then** the branch has exactly one row and its Repository cell reads "No repositories".
3. **Given** a branch not synced with Git that has read-only repositories, **When** the list renders, **Then** those repositories are listed as rows like any other.
4. **Given** the operator lacks permission to read a branch's repositories, **When** the list renders, **Then** that branch has exactly one row, its branch cells render normally, and its Repository cell reads "No permission" in a muted style; no other branch is affected.
5. **Given** repository data for a branch fails to load, **When** the list renders, **Then** that branch has exactly one row, its branch cells render normally, its Repository cell reads "Could not load repositories" in a muted style, and no toast or page-level error appears.

---

### Edge Cases

- A repository whose Git state has no colour defined in the schema: the pill falls back to a neutral style and still shows the state's value (or its label if there is no value), as the branch details page's pill already does.
- A repository row with no commit yet: the Commit cell is blank, with no copy control.
- A freshly created synced branch reports the default branch's fork-point commit; it is displayed as returned, not treated as empty.
- A branch whose repositories change from loading to N rows: the row count grows in place; the branch keeps its position in the list; rows below it move down.
- Short pending rows may let the infinite scroll request the next page earlier than today; accepted.
- A repository that is currently syncing: its row keeps refreshing at the same cadence the branch details page already uses, and stops when the sync settles.
- The default branch: it stays first in the list and fans out like any other branch.
- Existing filters (status, name, created-by, dates) continue to filter by branch; no filter or sort is offered on the three new columns.
- Column count changes: the table's column layout accommodates the three new columns without misplacing the existing ones.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The branches list MUST show three additional columns, in this order after "Proposed changes": "Repository", "Git state", "Commit".
- **FR-002**: For each branch, the list MUST show one row per Git repository visible on that branch, each row carrying the branch's existing cells plus that repository's name, Git state and imported commit.
- **FR-003**: The set of repositories shown for a branch MUST be what the backend returns for that branch. The list MUST NOT re-derive that set on the client from the branch's sync flag or status.
- **FR-004**: The Git state MUST be the repository's `sync_status` as resolved on that branch, rendered with the label, colour and description defined in the schema. When no colour is defined, the pill MUST fall back to a neutral style and still show the state's value or label, identically to the branch details page's pill.
- **FR-005**: The Commit cell MUST show the first 7 characters of the imported commit in a monospace face, expose the full hash on hover, and offer a copy control that copies the full hash. When there is no commit, the cell MUST be blank.
- **FR-006**: The Repository cell MUST show the repository's name as a link to that repository's page opened on the row's branch, and MUST mark read-only repositories with the same "Read-only" marker the branch details page uses.
- **FR-006a**: Within a branch, repository rows MUST be ordered by the same rule as the branch details page: repositories whose last import failed first, then repositories whose remote is unreachable, then the rest, each group sorted by repository name (case-insensitive). The unreachable status itself is not shown (FR-016); it only affects order. The anchor row of a branch may therefore change when a repository's reachability changes; selection is keyed by branch and is unaffected.
- **FR-007**: A branch that returns zero repositories MUST occupy exactly one row. Its Repository cell MUST read "Not synced with Git" when the branch is not synced with Git and "No repositories" otherwise, in muted text (`text-foreground-muted`); its Git state and Commit cells MUST be blank.
- **FR-008**: Selection MUST be per branch: ticking any row of a branch selects the branch, all of its rows show as selected, the selection count reports branches, and bulk actions receive each branch once. Only the checkbox on a branch's first row is in the keyboard tab order, named "Select <branch>"; the checkboxes on its other rows are skipped by Tab and named "Select <branch> (<repository name>)". The other repeated branch controls (the branch name link, the proposed-changes pill and the actions menu) are likewise in the tab order on the first row only. The commit copy button stays in the tab order on every row.
- **FR-009**: Shift-click range selection MUST continue to work and MUST count branches, not rows.
- **FR-010**: Pagination MUST continue to count branches per page; a page with N branches renders at least N rows.
- **FR-011**: Repository data MUST load per branch, after the branch rows are shown: branch cells render immediately, and the Repository cell shows a loading indicator until that branch's data arrives; Git state and Commit stay blank until then.
- **FR-012**: When the operator lacks permission to read a branch's repositories, that branch MUST render exactly one row with its branch cells intact and a muted (`text-foreground-muted`) "No permission" text in the Repository cell. No other branch is affected and no page-level error is shown.
- **FR-013**: When repository data for a branch fails to load for any other reason, that branch MUST render exactly one row with a muted (`text-foreground-muted`) "Could not load repositories" text in the Repository cell, without toasts or page-level errors. The load error's message MUST stay reachable: it is shown as a tooltip on that text for pointer users and rendered as visually hidden text alongside it for keyboard and screen-reader users. The branch details card's failed state shows the same message.
- **FR-014**: A repository that is currently syncing MUST keep its row's Git state and commit refreshing at the cadence already used by the branch details page, and stop when the sync settles.
- **FR-015**: The three new columns MUST NOT be filterable or sortable in this feature. Existing filters and the default ordering (default branch first, then by name) are unchanged.
- **FR-016**: The list MUST NOT show an upstream commit, a "behind by N" figure, a last-import time, or the repository's operational (remote reachability) status.
- **FR-017**: The three new columns MUST always be shown; no column-hiding control is added to the branches list.

### Key Entities *(include if feature involves data)*

- **Branch row**: one line of the table. Identified by the pair (branch, repository), or (branch, none) when the branch has no repositories or its repository data is loading, denied or failed. Carries the branch's existing attributes and the repository's Git state and commit.
- **Repository on a branch**: a Git repository as seen from one branch: name, kind (read/write or read-only), Git state (`sync_status`: value, label, colour, description) and imported commit. Already modelled by PR #10779 for the branch details page.
- **Git state**: the outcome of the repository's last import on that branch, as a schema-defined dropdown value. Distinct from the branch's own lifecycle status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can identify every branch whose repository import failed by scanning the branches list, with zero branch or repository pages opened.
- **SC-002**: A branch with N repositories appears on exactly N rows; a branch with none appears on exactly 1 row, with the explicit empty text and never a dash.
- **SC-003**: Selecting a multi-repository branch and running bulk delete acts on exactly one branch; the selection count matches the number of distinct branches selected.
- **SC-004**: Branch name, status and proposed-change cells are rendered before any repository data resolves; the new cells fill in afterwards without shifting any column horizontally. Rows below a branch may move down when its repositories arrive.
- **SC-005**: A permission or load failure on one branch's repositories leaves every other row of the list fully rendered.
- **SC-006**: Every state in this spec (loaded, loading, empty for both texts, denied, failed, no colour, no commit) has an automated test; the frontend lint, unused-code, type-regression and unit test gates pass.
- **SC-007**: Resolving one branch's repositories re-renders that branch's rows only; a window refocus issues at most one repository request per loaded branch.

## Assumptions

- The branch details work (PR #10779) is the base and merges before this feature. Its per-branch repository query, model, Git state pill and test fixtures are reused unchanged; this feature adds no second way of fetching or rendering repository state.
- The commit display component from PR #10658 is lifted byte-identical at its path so that the eventual merge of both branches is conflict-free. This is stated in the PR description.
- Repository data is fetched once per visible branch (about 40 requests per page of 40 branches) using the branch details page's query, so both pages share one cache. A per-repository or single-request alternative is a follow-up if profiling calls for it.
- The row set per branch follows the backend: a read/write repository appears only on branches synced with Git; a read-only repository appears on every branch. The list displays the branch's sync flag only to choose the empty-state wording.
- A read-only repository appears on every branch, so with R read-only repositories every branch has at least R rows. The owner accepts this multiplier; it is the backend's row set.
- Merged and deleting branches, if shown by the current list filters, fan out like any other branch; whatever repositories the backend returns for them are shown.
- The epic spec (`dev/specs/infp-671-cross-branch-repo-status/spec.md`) lists "extra columns on the global branches view" as out of scope for the backend query work; this ticket is the frontend follow-up that supersedes that line and adds no backend change.
- The branches table is rendered only by the branches page, so no other screen changes.
- When the backend truncates a branch's repository list, the list shows only the returned repositories, with no "more" marker.
- Out of scope: "Upstream" and "Last import" columns (IFC-3146, IFC-3147), the repository's operational status (unreachable remote), filters or sorting on the new columns, column hiding, any backend change, the branch-details page itself, and resolving the visual similarity between the branch "Status" pill and the "Git state" pill beyond keeping them separated by the "Proposed changes" column and using different pill shapes.
