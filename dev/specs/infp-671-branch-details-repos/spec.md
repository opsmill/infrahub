# Feature Specification: Branch details — Git repositories and tasks

**Feature Branch**: `ple-branch-details-repos-infp-671` (based on `cross-branch-repo-status-infp-671`)

**Created**: 2026-09-29

**Status**: Draft

**Jira**: [INFP-671](https://opsmill.atlassian.net/browse/INFP-671) (Git repository sync visibility)

**Source design (PRD)**: `design/05-handoff.md` (proposal, decisions, open questions, system gaps, lift sheet, queries), with `design/00-brief.md`, `design/03-decisions.md` and `design/04-review.md`. Prototype: `ple-design-branch-details-repos`, `frontend/app/src/pages/_proto/branch-details/revs/rev-06/` (Object layout, rev 6).

**Builds on**: `dev/specs/infp-671-cross-branch-repo-status/` (the `InfrahubRepositoryBranchStatus` query, IFC-3127/3128/3129). That query reads one repository across every branch; this page needs every repository on one branch, so it is not reused as a data source, but its rules carry over: Git state comes from `sync_status` with the schema's own label and colour, attribute `updated_at` is never shown as a "last import" time, and a caller without repository permission is denied rather than shown a trimmed list.

**Input**: User description: "The branch details page shows the branch's Git repositories and its tasks, in the object details page layout. The Git repositories card has one row per repository: name, Read-only tag, Git state (sync_status) and commit. Failing repositories sort first, and the table paginates at 10 rows with a fixed height. Under the table sit an import error band per failing repository (the raw last error log line of its latest import task, and a link to that task's details page) and a remote-unreachable band for operational_status error-cred, error-connection or error. After 3 bands the rest collapse behind Show all. It has empty, loading and no-permission states. Today's inline branch action buttons (Merge, Propose change, Rebase, Validate, Delete) sit below the repositories card, and Merge is not gated. Below them is a paginated tasks table (Title, State, Workflow, Related, Updated) of branch and repository tasks, where each title links to /tasks/<id>, with loading, empty and failed-to-load states. The header matches the object page: name, copy, status badge, description and refresh. Epic INFP-671. The source design is in dev/specs/infp-671-branch-details-repos/design/ (05-handoff.md, including the lift sheet and queries, plus 00-brief.md, 03-decisions.md and 04-review.md)."

## Problem Statement

Someone merged a branch from the branch page while a generator had failed on it, and the artifacts came out stale. Today the branch page says nothing about the branch's Git repositories: to learn whether an import failed or a generator broke, an engineer opens each repository page and then the Tasks page, one by one. People merge from the branch page without a proposed change, so the proposed change's checks never run.

This feature puts that evidence on the branch page, directly above the Merge button: every repository's Git state and commit on the branch, the raw error of each failed import, a warning when Infrahub can't reach a remote, and one table of every task that ran on the branch. It also brings the page into line with the object details page (header, tabs, body card, cards), so it reads like every other detail page.

It does **not** block or warn on Merge (see Clarifications).

## Clarifications

### Session 2026-09-29

Decisions taken autonomously for this run, from the design handoff's open questions and the round-6 owner decisions. Items marked **needs sign-off** stand as the default until the named owner confirms.

- Q: Is Merge gated by import errors, failed generators or running tasks? → A: **No.** Merge keeps today's behaviour. Failures are shown on the page, above the button, and never disable, restyle or add a confirmation to it. This reverses brief decisions #1 and #3 (`design/00-brief.md`), per the owner's round-6 call ("merges aren't blocked"; INFP-670 has no backend gate and a UI-only gate protects nobody who merges through the API, SDK or CI). **Open question 1 carried forward, needs sign-off from the INFP-670 owner:** "With Merge ungated, is the incident covered, or does this wait for INFP-670's backend gate?" Default: ship ungated, visibility only.
- Q: Does this card extend IFC-3200's Git repositories card or replace it? (handoff open question 2) → A: IFC-3200's card is not on this base branch (no Git repositories card exists in the frontend here; the only related UI is the homepage repositories widget). The card is built once, as a reusable entity component in the repository entity, taking the branch as an input, so IFC-3200 adopts it instead of building a second one.
- Q: Which tasks does the Tasks table show? (open question 3) → A: Every task the task manager tags with this branch, newest first, paginated by the server (10 per page, with the server's total count). No workflow allow-list. The task manager caps one page at 200 tasks; 10 is well under it.
- Q: Are read-only repositories included? (open question 4) → A: Yes, with a "Read-only" tag on the row.
- Q: What does the card show on a branch with Sync with Git off? → A: Read-write repositories do not import on such a branch, so they are not listed there; read-only repositories still track every branch, so they are. If that leaves no rows, the card shows the "Not synchronised with Git" empty state. This matches the row set the cross-branch status query already uses (`infp-671-cross-branch-repo-status/spec.md`, FR-002).
- Q: Does the default branch get the new cards? → A: No. The default branch keeps today's Details tab (the Details card only, no actions, no tasks), and has no tabs, as today. The new cards appear wherever today's action row and task list appear: on non-default branches.
- Q: Does the repository row keep the prototype's "⋯" menu? → A: No. Its items were stubs ("Reimport last commit" was a toast, "View tasks" had no target). The repository name links to the repository's page; that is the row's only action.
- Q: Without permission to view repositories, what does the Tasks table show? → A: Every task on the branch, as for anyone else. The task list is not filtered by repository permission on the server, and hiding repository tasks on the client would break the server's pagination and count. The Related cell shows the related object's kind instead of a repository name it could not load. (This departs from `design/04-review.md` 4c, which hid repository tasks in the mock.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every repository's Git state before merging (Priority: P1)

An engineer opens the branch they are about to merge. Below the branch's details, a Git repositories card lists every repository on that branch with its name, a Read-only tag where it applies, its Git state on this branch and the commit it has imported. Repositories in trouble come first, so a failed import is on the first page even when the branch has 40 repositories.

**Why this priority**: This is the evidence people collect by hand today, one repository page at a time. Without it nothing else on the page helps.

**Independent Test**: Seed a branch with 12 repositories, one of them in Import Error and one read-only. Open the branch page: the failing repository is the first row, the read-only one carries its tag, every row shows its Git state label and colour from the schema and its commit, and the table shows 10 rows with a pager.

**Acceptance Scenarios**:

1. **Given** a non-default branch that syncs with Git and has 4 repositories, **When** the user opens its Details tab, **Then** the Git repositories card lists 4 rows, each with the repository name (linking to the repository's page), its Git state on this branch (the label and colour defined for that `sync_status` value in the schema), and its commit, and the card header shows the count 4.
2. **Given** a read-only repository, **When** it is listed, **Then** its row carries a "Read-only" tag next to the name.
3. **Given** 40 repositories of which the 17th by name is in Import Error, **When** the page opens, **Then** that repository is on page 1, above every repository that is not failing.
4. **Given** 11 repositories, **When** the user moves from page 1 to page 2, **Then** page 2 shows 1 row, the table keeps the same height as page 1, and the controls below the card do not move.
5. **Given** exactly 10 repositories, **When** the page opens, **Then** all 10 rows show and there is no pager.
6. **Given** the repositories are still loading, **When** the page renders, **Then** the card shows placeholder rows at the real row height and no count.
7. **Given** a user who is not allowed to view repositories, **When** the page opens, **Then** the card says they don't have access to the branch's repositories, and shows no rows and no count.
8. **Given** a branch with Sync with Git off and no read-only repositories, **When** the page opens, **Then** the card says the branch is not synchronised with Git, with a one-line reason.
9. **Given** an instance with no Git repositories at all on a branch that syncs with Git, **When** the page opens, **Then** the card says no Git repositories are connected.

---

### User Story 2 - Read why an import failed, and reach its log (Priority: P1)

For each repository whose import failed on the branch, a red band under the table names the repository and shows the raw last error line from its latest import task, with a link to that task's details page. For a repository Infrahub can't reach (bad credentials, no connection, remote error), an amber band says the commit shown may be out of date and links to the repository.

**Why this priority**: The Git state says that an import failed; the band says why, which is what the engineer needs to decide whether to merge. It is P1 alongside Story 1 because the incident was a failure nobody read.

**Independent Test**: Seed a branch where one repository's latest import failed with a known error log line and another repository has `operational_status` `error-cred`. Open the page: a red band shows the first repository's error line verbatim and "View task log" opens that task; an amber band names the second repository and "Open repository" opens it.

**Acceptance Scenarios**:

1. **Given** a repository in Import Error on the branch whose latest import task logged an error line, **When** the page opens, **Then** a red band under the table shows "<repository> — import failed", the last error-level line of that task's log verbatim in monospace (line breaks kept), and a "View task log" link to that task's details page.
2. **Given** a repository in Import Error for which no import task, or no error-level log line, can be found on this branch, **When** the page opens, **Then** its band still shows, says the error details couldn't be found, and links to the repository instead of a task.
3. **Given** a repository whose `operational_status` is `error-cred`, `error-connection` or `error`, **When** the page opens, **Then** its row shows a warning icon with an accessible label naming the problem, and an amber band says Infrahub can't fetch new commits so the commit shown may be out of date, with an "Open repository" link.
4. **Given** 5 repositories with bands, **When** the page opens, **Then** the first 3 bands show, followed by a line reading "2 more repositories with errors:" and their names, with a "Show all" control; **When** the user activates it, **Then** all 5 bands show and the control reads "Collapse".
5. **Given** a repository that is both in Import Error and unreachable, **When** the page opens, **Then** it gets one band, the import error band, and its row still shows the unreachable icon.
6. **Given** the error line of a band is still loading, **When** the page renders, **Then** the band shows the repository name and a loading line, and the rest of the card is already usable.

---

### User Story 3 - Act on the branch from the same place (Priority: P1)

Today's inline branch actions — Merge, Propose change, Rebase, Validate, Delete — sit directly below the repositories card, so the evidence is read before the button that ignores it.

**Why this priority**: The actions exist today; moving them must not break them. Losing Merge or Delete would be a regression.

**Independent Test**: On a non-default branch with a failing import, all five buttons render below the repositories card, in today's order, and each behaves exactly as it does today; Merge is enabled and merges.

**Acceptance Scenarios**:

1. **Given** a non-default branch, **When** the Details tab renders, **Then** the five buttons appear below the Git repositories card and above the Tasks card, in the order Merge, Propose change, Rebase, Validate, Delete.
2. **Given** a repository in Import Error, a failed task and a running task on the branch, **When** the user activates Merge, **Then** the merge runs exactly as it does today: no disabled state, no warning text on or next to the button, no acknowledgement, no extra dialog.
3. **Given** the default branch, **When** its Details tab renders, **Then** no action buttons show (as today).

---

### User Story 4 - See every task that ran on the branch (Priority: P2)

A Tasks card lists branch and repository tasks in one paginated table: Title, State, Workflow, Related, Updated. Each title links to that task's details page, where the logs are. The header shows the total, the number of failed tasks and an "Open in Tasks" link.

**Why this priority**: The failed generator from the incident shows up here, not in the repositories card. It is P2 because the repositories card already covers import failures, and today's accordion already lists some branch tasks.

**Independent Test**: Seed a branch with 12 tasks (imports, a failed generator, validate, rebase). The Tasks card shows 10 rows newest first, a pager to page 2, the total 12 and "1 failed", and the failed generator's title opens `/tasks/<its id>`.

**Acceptance Scenarios**:

1. **Given** 12 tasks on the branch, **When** the page opens, **Then** the Tasks card shows the 10 most recent, a pager, the count 12 in its header and the number of failed tasks next to it.
2. **Given** a row, **When** the user activates its title, **Then** the task details page for that task id opens.
3. **Given** a task related to a repository listed in the Git repositories card, **When** it is shown, **Then** Related shows the repository's name; a task with no related object shows "This branch"; a task related to any other object shows that object's kind.
4. **Given** a task whose workflow has a known short label (import, generator, artifacts, validate, rebase, merge, sync), **When** it is shown, **Then** Workflow shows that label; otherwise it shows the workflow identifier unchanged.
5. **Given** the tasks are loading, **When** the page renders, **Then** the card shows placeholder rows and no count.
6. **Given** no task has run on the branch, **When** the page opens, **Then** the card says so and explains what will appear there.
7. **Given** the task query fails, **When** the page renders, **Then** the card says the task results didn't load, and the rest of the page is unaffected.
8. **Given** 11 tasks, **When** the user moves to page 2, **Then** the table keeps the height of page 1.

---

### User Story 5 - A branch page that looks like every other detail page (Priority: P3)

The branch page header matches the object details page: the branch name, a copy button, the status badge, the description, and a Refresh button on the right. The tabs and the body use the object page's layers, and the Details card keeps today's attributes.

**Why this priority**: Consistency, and a single Refresh for the whole page. The page works without it.

**Independent Test**: Open a branch page and an object page side by side: header row, tab row and body card use the same structure and styling. Refresh re-fetches the branch details, repositories, import errors and tasks.

**Acceptance Scenarios**:

1. **Given** any branch, **When** its page opens, **Then** the header shows the name, a copy button with the accessible name "Copy branch name", the branch's metadata popover as today, the status badge (or the default badge on the default branch), the description when there is one, and a Refresh button at the end of the row.
2. **Given** the user activates Refresh, **When** the data returns, **Then** the branch details, the repositories, the import error lines and the tasks have all been fetched again, and the button shows it is busy until they have.
3. **Given** the "You're working on this branch" notice applies, **When** the page opens, **Then** it shows above the header, as today.
4. **Given** the Details tab of a non-default branch, **Then** the order is: Details card (today's attributes, unchanged) → Git repositories → actions → Tasks.

---

### Edge Cases

- **Import task not tagged with the repository.** Some import flows tag their task with the branch only, or the repository only (see `research.md`). When the latest import task can't be found, the band still shows, without an error line, and links to the repository (US2 scenario 2). It never disappears.
- **Long error line.** Shown in full, wrapped, line breaks preserved. It is not truncated.
- **Very long repository or branch names.** Truncated with the full name available on hover; the Read-only tag and Git state stay visible.
- **A repository whose `sync_status` has no schema colour or label.** Shows the raw value in a neutral tag.
- **Missing commit.** A repository that has never imported shows an empty-value placeholder, not an error.
- **The page changes between pages.** If the number of repositories or tasks drops so the current page no longer exists, the table moves to the last page that does.
- **A page number in the URL that doesn't exist** (0, negative, past the end, not a number): the table shows the nearest valid page.
- **Running tasks.** Running and pending tasks show their state and refresh on their own; nothing on the page waits for them.
- **More repositories than one request returns.** Beyond the fetch limit (see plan) the card says only the first N are shown and links to the repository list.
- **Unknown Git state or unknown operational status** (`unknown`) is not treated as failing.
- **Denied, then granted.** Permission is re-checked on Refresh.
- **Tasks related to several objects.** Related shows the first repository among them, otherwise the first object's kind.

## Requirements *(mandatory)*

### Functional Requirements

#### Page layout and header

- **FR-001**: The branch page header MUST show, in one row: the branch name, a copy-to-clipboard button for the name with the accessible name "Copy branch name", the branch metadata popover (as today), the branch status badge (or the default-branch badge), and a Refresh button at the end of the row. The branch description, when present, MUST show under the row.
- **FR-002**: The "You're working on this branch" notice MUST keep showing above the header under today's conditions.
- **FR-003**: The tab row and the tab body MUST use the object details page's structure and styling (tab row above a body card). The tabs and their routes are unchanged.
- **FR-004**: Refresh MUST re-fetch the branch details, the repositories, the import error lines and the tasks, and MUST show a busy state until they have all returned.
- **FR-005**: On a non-default branch, the Details tab MUST show, top to bottom: the Details card (today's attributes, content unchanged, in an object-style card with a "Details" header), the Git repositories card, the branch action buttons, and the Tasks card. On the default branch it MUST show the Details card only.

#### Git repositories card

- **FR-010**: The card MUST list one row per repository on the branch. On a branch with Sync with Git on, that is every repository (read-write and read-only). On a branch with Sync with Git off, that is the read-only repositories only.
- **FR-011**: Each row MUST show: the repository name, linking to the repository's details page; a "Read-only" tag when the repository is read-only; its Git state on this branch, rendered with the label and colour the schema defines for that `sync_status` value; its commit on this branch, in monospace, truncated with the full value available on hover.
- **FR-012**: A row whose `operational_status` is `error-cred`, `error-connection` or `error` MUST show a warning icon next to its Git state, with an accessible label naming the problem.
- **FR-013**: Rows MUST be ordered: repositories in Import Error first, then unreachable repositories (FR-012), then the rest; by name within each group.
- **FR-014**: The table MUST show at most 10 rows per page. When there is more than one page, it MUST show a pager (previous, next, page numbers, and "Showing X to Y of Z"), and the table MUST keep the height of a full page on every page. With 10 rows or fewer there MUST be no pager.
- **FR-015**: The current page MUST be kept in the URL, so reloading or sharing the link opens the same page. An invalid or out-of-range page MUST resolve to the nearest valid page.
- **FR-016**: The card header MUST show the number of repositories once they have loaded.
- **FR-017**: While loading, the card MUST show three placeholder rows at the real row height, marked as busy for assistive technology.
- **FR-018**: A user without permission to view repositories on this branch MUST see a no-access message in the card, with no rows and no count.
- **FR-019**: When there are no rows, the card MUST show "Not synchronised with Git" with a one-line reason on a branch with Sync with Git off, and a "No Git repositories" message otherwise.
- **FR-020**: When the repository query fails for any reason other than permission, the card MUST say the repositories couldn't be loaded, without affecting the rest of the page.

#### Error bands

- **FR-021**: For each repository in Import Error, the card MUST show a red band under the table with the repository name, "import failed", the last error-level log line of the repository's latest import task on this branch shown verbatim in monospace with line breaks kept, and a "View task log" link to that task's details page (`/tasks/<task id>`, keeping the branch context).
- **FR-022**: When no import task, or no error-level log line, is found for a failing repository, its band MUST still show, say that the error details couldn't be found, and link to the repository's page instead.
- **FR-023**: For each unreachable repository (FR-012) that is not in Import Error, the card MUST show an amber band with the repository name, the problem, the sentence "Infrahub can't fetch new commits, so the commit shown may be out of date." and an "Open repository" link.
- **FR-024**: Bands MUST follow the row order of FR-013 and MUST cover every failing repository, not only those on the current page.
- **FR-025**: When there are more than 3 bands, only the first 3 MUST show, followed by a summary line "<N> more repositories with errors: <names>" (singular for 1) and a "Show all" control, which expands every band and then reads "Collapse".
- **FR-026**: An error line still loading MUST NOT hold back the table or the other bands; its band shows a loading line until it arrives.

#### Branch actions

- **FR-030**: The five existing action buttons (Merge, Propose change, Rebase, Validate, Delete) MUST show below the Git repositories card, in that order, with today's behaviour, labels and permission rules.
- **FR-031**: Merge MUST NOT be disabled, restyled, relabelled, wrapped in a confirmation, or accompanied by a warning because of repository states, import errors, operational status, or task states.

#### Tasks card

- **FR-040**: The Tasks card MUST list every task the task manager associates with this branch, newest first, 10 per page, paginated and counted by the server.
- **FR-041**: Each row MUST show: Title, linking to that task's details page (`/tasks/<id>`, keeping the branch context), with the whole title cell as the target; State, using the app's existing task state badges; Workflow, as a short label for known workflows (Import, Generator, Artifacts, Validate, Rebase, Merge, Sync) or the raw workflow identifier otherwise; Related, as in US4 scenario 3; Updated, as a date in the app's date format.
- **FR-042**: The card header MUST show the total number of tasks once loaded, the number of failed tasks on the branch when it is above zero, and an "Open in Tasks" link to the Tasks page.
- **FR-043**: Pagination MUST follow FR-014 and FR-015, with its own page parameter, independent of the repositories table.
- **FR-044**: The card MUST have a loading state (placeholder rows, no count), an empty state that explains which tasks will appear, and a failed-to-load state that says the task results didn't load. None of them affect the rest of the page.
- **FR-045**: Rows MUST NOT expand; the logs live on the task details page.
- **FR-046**: Running tasks MUST update on the page without a manual refresh, at least as often as today's task list does (every few seconds while tasks are running, or on a fixed interval).

#### Presentation

- **FR-050**: All colours on the new and changed parts of the page MUST come from the design system's theme tokens (or, for the Git state, from the schema's colour), so the page renders correctly in light and dark themes. No hard-coded hex colours from the prototype.
- **FR-051**: The page targets desktop widths. Tables MAY scroll horizontally in narrow containers; no mobile layout is required.
- **FR-052**: Every interactive element (links, pager buttons, Show all, Refresh, copy) MUST be reachable by keyboard in visual order and have an accessible name.

### Key Entities

- **Repository on a branch**: A Git repository (read-write or read-only) as seen from one branch. Name, kind (read-only or not), Git state on this branch (`sync_status`, with its schema label and colour), commit on this branch, and operational status (whether Infrahub can reach the remote; the same on every branch).
- **Import task**: The latest task that imported a repository on this branch. Its id (for the link) and its log lines, of which the last error-level one is shown.
- **Branch task**: Any task the task manager tags with the branch: title, state, workflow, related objects, last update time.
- **Branch**: Name, description, status, default flag, Sync with Git flag, and today's attributes. Unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the branch page, an engineer can name every repository in Import Error on the branch and read its last error line without navigating anywhere (0 extra pages, down from 1 per repository plus the Tasks page today).
- **SC-002**: A failing repository is on the first page of the repositories table for any number of repositories up to the fetch limit.
- **SC-003**: Paging through either table never moves the elements below it (0px shift between pages).
- **SC-004**: Every task that ran on the branch is reachable from the page in one click from its row.
- **SC-005**: Merge behaves identically to today in every repository and task state (no added clicks, no disabled state).
- **SC-006**: The new parts of the page have no hard-coded colours and pass a visual check in both themes.

## Assumptions

- The repository nodes are visible from every branch, and `sync_status` and `commit` resolve per branch, as the cross-branch status spec establishes.
- A branch has at most a few hundred repositories, so the card can load them in one request and order them on the client (see `plan.md`); the fetch limit is a planning constant with a visible notice when exceeded.
- The task details page (`/tasks/<id>`) already shows a task's logs.
- The existing action buttons and their permission handling are reused unchanged.
- The theme tokens and theme provider exist on this base branch (`frontend/packages/ui/src/theme`, `styles/theme.css`).
- The shared table pagination from IFC-3130 is not on this base branch; it is added here as a shared component based on the prototype's copy.
- IFC-3200 and IFC-3199's frontend (header indicator) are not on this base branch; nothing of theirs is reused.

## Dependencies

- `INFP-670` owner sign-off on shipping Merge ungated (Clarifications, open question 1).
- Better import error text is IFC-3034; this feature shows the raw log line until then.
- A backend `last_import_task` field on the repository, and tagging every import flow with both the branch and the repository, would make the band's lookup exact. Both are follow-ups, not blockers (`research.md`).

## Out of Scope

- Gating, warning on, or confirming Merge (INFP-670 backend gate).
- An Upstream column, "N behind", or a Last import column (IFC-3146, IFC-3147, IFC-3154; no backend field today).
- Structured import error messages (`TaskError` is only filled for webhook tasks; IFC-3034).
- Expandable task rows or an inline log viewer.
- A per-repository row menu, reimport or reconnect actions.
- Generator or artifact readiness summaries, readiness verdicts, and a merge rail (rejected directions in `design/05-handoff.md` §3).
- Mobile layout.
- Changes to the Data, Files, Artifacts and Schema tabs.
- Fixing the shared `CopyToClipboardButton`'s missing default accessible name (this page passes one).
