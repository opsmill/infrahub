# 01 — System inventory

Sources:
- the design-system component list (`frontend/packages/ui/src/index.ts`)
- `dev/knowledge/frontend/design-system.md`
- `dev/knowledge/frontend/shared-components.md`
- the current branch page (`src/pages/branches/details.tsx`, `src/entities/branches/ui/`)
- the backend task and repository code (`backend/infrahub/git/tasks.py`, `generators/tasks.py`,
  `artifacts/tasks.py`, `core/constants/__init__.py`)

The screen is made of three things: the branch header and actions, the Merge warning, and a
repository section with one row per repo plus an Artifacts row.

## Covered: use as-is

### `@infrahub/ui`

| Component | Where it goes |
|---|---|
| `Button`, `LinkButton` (`variant="active"`, `outline`, `size="sm"`) | Merge, Propose change, Rebase, Validate and Delete (as today). "View logs" and "Open repository" links on repo rows. |
| `Card`, `CardHeader`, `CardContent` | Attributes surface, repository section surface. |
| `Modal`, `ModalOverlay` | The Merge warning step if it's a dialog. Precedent: `entities/branches/ui/modal-delete-branch.tsx`. |
| `Popover`, `PopoverDialog`, `PopoverTrigger` | The Merge warning if it's attached to the button rather than a dialog. |
| `Tooltip` | Commit hash, full sync time, repo status descriptions. |
| `Spinner` | Loading state per row and on the Merge action while readiness loads. |
| `Menu`, `MenuTrigger`, `MenuItem` | Per-repo overflow actions (reimport last commit, check connectivity), which already exist in `entities/repository/ui/repository-menu-section.tsx`. |
| `Meter` | Optional. "3 of 5 repos passing" summary. |
| `ScrollArea` | Long repo list when there are many repositories. |

### `src/shared/components`

| Component | Where it goes |
|---|---|
| `Badge` (`shared/components/ui/badge.tsx`), variants `green`, `red`, `yellow`, `blue`, `gray`, `*-outline` | Task state and repo sync state. It covers every state we need, and no new colour tokens are required. |
| `Alert` (`shared/components/ui/alert.tsx`) | Toasts after merge, as today. |
| `Accordion` (`shared/components/display/accordion.tsx`) | Collapsible repo rows, and the existing branch tasks section. |
| `DateDisplay` (`shared/components/display/date-display.tsx`) | Sync time, last rebase, `created_at` (fetched today, not shown). |
| `DurationDisplay` | Run duration on the latest task per workflow. |
| `Row` / `Col` (`shared/components/container.tsx`) | Layout. |
| `LinkTab` (`shared/components/ui/link.tsx`) | The existing branch tabs, plus a new "Repositories" tab if a direction uses one. |
| `Pulse` (`shared/components/ui/pulse.tsx`) | "Still running" indicator. The global `TaskStatus` button already uses it. |
| `NoDataFound`, `ErrorScreen`, `LoadingIndicator` | Empty, error and loading states. |

### Existing page patterns

- **Detail-page tabs:** `BranchTabs`, `useBranchDetailsOutlet()` and `branch-urls.ts`. A
  Repositories tab slots in as another child route of `/branches/:branchName` in
  `src/app/router.tsx`.
- **Merge button disabled logic:** `branch-merge-button.tsx` already queries ongoing tasks
  (`GET_BRANCH_ACTION_STATE`, polled every 5s). The warning hooks into the same `onPress`.
- **Task log view:** `TaskDisplay` and `Logs` (`entities/tasks/ui/task-display.tsx`, `logs.tsx`)
  render a task with its state badge and logs. `getLogBadge` maps a task state to a badge.
- **Task table:** `TaskItems` (`entities/tasks/ui/task-items.tsx`) renders title, branch, state,
  related nodes, progress, workflow and updated-at. It's filterable by branch and
  `related_node__ids`.
- **Task links:** `/tasks/:taskId` and the object-page tasks tab
  (`pages/objects/object-details/tasks.tsx`) are where "View logs" links land.
- **Repo list:** `GitRepositoryItem` (`entities/homepage/ui/git-repository.tsx`) is a `ListBoxItem`
  with a sync-status pill coloured from the schema dropdown's `color`.
- **Repo sync states**, from the backend enums:
  - `sync_status`: unknown, in-sync, error-import, syncing
  - `operational_status`: unknown, error-cred, error-connection, error, online
  - `internal_status`: active, inactive, staging

## Close: exists but doesn't fit

| Thing | What's missing |
|---|---|
| `GitRepositoryItem` (homepage widget) | Shows `sync_status` only. There's no commit, sync time, `operational_status` or per-workflow task state. It's also a `ListBoxItem`, a selection primitive, which is the wrong semantics for a status row with links inside. Reuse the pill-colouring approach, not the component. |
| `TaskDisplay` (branch tasks accordion today) | Lists every task as a card. The brief needs only the **latest run per workflow**, grouped under a repo. The card with its logs is still the right view once a row is expanded. |
| `TaskItems` (task table) | Right columns, wrong grouping. It's flat and has no "latest per workflow" collapse. The link target it produces is what "View all tasks" should point at. |
| Files tab repo sections (`entities/diff/ui/file-diff/file-repo-diff.tsx`) | Already groups by repo with `commit_from` and `commit_to`, but it's a file diff. There's no status and no tasks. It's a precedent for how a repo row names itself and shows a commit range. |
| `checks-summary.tsx` + `PieChart` (proposed change Checks tab) | A status roll-up for validators. The idea of summing up a status is close, but it's built around validators and proposed changes, and a pie chart is the wrong shape for "3 repos, one failed". |
| `BranchMergeButton` | Blocks only while a merge is already running. It has no warning step and no idea of repo readiness. Needs a confirm step, which `Modal` covers. |
| `GET_BRANCH_DETAILS` query | Fetches `origin_branch` and `created_at` but the page doesn't show them. No repo data. |

## Missing: nothing covers this

| Gap | What it would take |
|---|---|
| **Readiness data: "latest run per repo and workflow on this branch"** | No query exists. The prototype builds it in the frontend: fetch `InfrahubTask(branch)` for repo-related workflows, then group by `related_node` (git tasks), by `GeneratorDefinition.repository` (generator tasks), or into a single "Artifacts" bucket (artifact tasks, which are tagged only with the target node). The real version is a backend query, recorded as a follow-up in `00-brief.md`. |
| **Repo query with commit, operational status and sync time** | The frontend queries `commit`, `operational_status` and `internal_status` nowhere. A `CoreGenericRepository` query on the branch is needed. Whether a "sync time" field exists on the repo node is **unverified**. If it doesn't, the best available stand-in is the latest import task's `updated_at`. |
| **Readiness summary / repo status row** | No component shows "entity + several labelled sub-states + a link each". It's built from `Card`, `Badge`, `Tooltip` and `LinkButton`. If it turns out to be reusable (proposed changes want the same thing), it's a candidate for `shared/components/display`, not `@infrahub/ui`. |
| **Prototype route** | The app has no prototype or playground route (`src/app/router.tsx` has none). Phase 2 adds one under the authenticated layout, for example `/_proto/branch-details`, with a `?variant=` switcher. It's deleted once the design is picked. |
| **Workflow display names** | Task titles are human-readable ("Import objects from git repository", "Generate artifact {name}"), but there's no frontend map from workflow ID to a short label such as Import, Generators, Checks, Artifacts. Needed for column or row labels. The prototype hardcodes it. The backend query should return it. |

## Workflows the readiness logic has to cover

Source: flow names in `backend/infrahub/git/tasks.py`, `generators/tasks.py`, `artifacts/tasks.py`
and `workflows/catalogue.py`.

| Group shown in the UI | Workflows | Tied to a repo by |
|---|---|---|
| Sync / import | `git_repositories_sync`, `git-repository-add-read-write`, `git-repository-add-read-only`, `git-repository-pull-read-only`, import last commit / import objects | `related_node` = repository ID |
| Checks | `git-repository-user-checks-definition-trigger`, `git-repository-trigger-user-checks`, `git-repository-trigger-internal-checks`, `git-repository-check-merge-conflict` | `related_node` = repository ID (mostly; confirm per flow) |
| Generators | `generator-definition-run`, `request-generator-definition-run`, `generator-run`, `run-generator-as-check` | generator definition ID → `GeneratorDefinition.repository`; some are tagged with the branch only (`add_tags(branches=[branch])` in `generators/tasks.py::run_generator_definition`) and can't be placed |
| Artifacts | `artifact-definition-generate`, `request_artifact_definitions_generate`, `artifact-generate` | Target node only. Goes in its own **Artifacts row**, not under a repo (per the brief). |
| Transforms | `transform_render_jinja2_template`, `transform_render_python` | Branch only: both flows call `add_branch_tag` (`transformations/tasks.py::transform_python`, `::transform_render_jinja2_template`), so they can't be tied to a repository. Probably out of the warning. **Open.** *(Corrected 2026-10-02: this row said `related_node` = transform ID and cited `computed_attribute/tasks.py:667`, which defines neither flow.)* |

## Worst-case data the prototype must render

- A branch with 12 repositories, one with a 60-character name like
  `network-automation-generators-emea-datacenter-fabric-templates`.
- A repo with `operational_status = error-cred` and `sync_status = error-import` at the same time.
- A read-only repo (`CoreReadOnlyRepository`) next to read-write repos.
- A generator task tagged only with the branch, which can't be tied to any repo.
- An Artifacts row where 180 of 300 artifact tasks failed.
- A repo with a failed generator on Monday, a passing re-run on Tuesday, and a failed check on
  Wednesday. Only Wednesday's failure counts.
- The readiness query itself failing, which must show "Couldn't check", never green.
- A branch with `sync_with_git = false` and no repos: the section explains why it's empty.
- The default branch: no Merge, no warning.
- A logged-out viewer: Merge disabled, as today.

## Ticket coverage for the Readiness rail (checked 2026-09-23 against INFP-671)

| Rail element | Status | Where it comes from |
|---|---|---|
| Repo rows: name, kind, commit, Git state (`sync_status`) | **Available now** | An ordinary repository query on the branch. IFC-3200 (In Progress) builds exactly these columns (`Repository, Kind, Tracking, Git state, Commit`) as a card below `BranchAttributes`. |
| Per-repo error line + link to the task log | **Coming soon** | IFC-3200 error bands (sections 4c/4d of the design canvas). Better error text: IFC-3034 (In Progress). |
| "Not synced with Git" empty state | **Coming soon** | IFC-3200, section 4d. |
| Last sync / last import time | **Not ticketed** | IFC-3200 defers `Last import` to a follow-up ticket that doesn't exist yet. IFC-3104 forbids wiring it to the attribute's `updated_at`. |
| Upstream head / "N behind" | **Soon, query only** | IFC-3146 (Done), IFC-3147 (In Progress), IFC-3154 (Draft). |
| Generators / Checks / Artifacts latest-run status | **Not in any ticket** | Frontend-only from `InfrahubTask` (the prototype's approach). The epics are driven by `sync_status`, and IFC-3199 says explicitly not to derive Git health from task state. |
| Verdict + Merge warning with override | **Goal, not ticketed** | INFP-670 ("a branch whose import failed is not mergeable"). Its open question 6, block or warn with override, is unanswered. PR #10619 (open) gates **proposed-change** merges only, and a direct `BranchMerge` bypasses it. |
| Moving the actions into the rail | **Waiting on design** | IFC-3202 (Draft) says the branch-actions and task-log redesign "needs a design pass before it can be specced". |
| Header "is Git broken" glyph | **In review** | IFC-3199. It overlaps with the rail's verdict. |

## IFC-3200 canvas: section 4, the branch detail view

Source: the "Git sync visibility" canvas (Wim, claude.ai/design project "Infrahub Git integration
improvements"). Read 2026-09-23. The file read is capped at 256 KiB, so **4d (no Git counterpart) and
4e (mixed read-only) were truncated** and are known only from IFC-3200's text.

- **Placement:** the attributes card is unchanged. A **Git repositories** card with a count sits
  directly below it, and the action row (Merge, Propose change, Rebase, Validate, Delete) and the
  Tasks accordion stay below that card.
- **Columns:** `Repository` (repo icon + link, truncated), `Git state` (the `sync_status` dropdown
  pill: blue "In Sync", red "Import Error" with a light red cell), `Commit` (teal-tinted cell,
  monospace, with an "↓ N behind" chip), `Upstream` (purple-tinted cell, monospace), `Last
  import` (relative time), and a trailing `⋮` row menu.
- **Error bands (4b/4c):** below the table, one red band per failing repository. Each has its title
  "<repo> — <reason>", a one-line cause with inline `code`, the line "The commit was fetched
  successfully; only the import failed", and a "View task log →" link. Repositories that are fine
  stay unmarked. At four or five failures, the canvas leaves stacked bands versus a single summary
  band as an open team decision.
- **Merge:** the 4b band says "Merging this branch is blocked until the import succeeds". The canvas
  itself flags as an open question whether Merge should be disabled with the reason attached or fail
  with an explanation. This conflicts with brief decision #3, which says to warn and never block.
- **Data availability:** `Upstream` and `Last import` wait on IFC-3146/IFC-3147 plus a follow-up
  ticket. IFC-3200 ships the other columns first, and rows must render without those two.
- **Not in the canvas:** generator, check or artifact status, and any readiness verdict or rail.
  Those are this design's additions (brief #8).
