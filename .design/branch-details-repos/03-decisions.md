# 03 — Decisions (refined: Readiness rail)

Prototype: `http://localhost:8080/_proto/branch-details`. Parameters:
- `?scenario=`: `incident`, `import-error`, `generator-failed`, `running`, `many-errors`,
  `tasks-unknown`, `all-clear`, `no-repos`, `loading`, `denied`
- `repos`, `repos_page`, `bands`, `rail`, `upstream=0|1`

Code: `frontend/app/src/pages/_proto/branch-details/`: `index.tsx`, `data.ts`,
`git-repositories-card.tsx`, `merge-rail.tsx`, `branch-actions-menu.tsx`, `table-pagination.tsx`.
The Checkpoint, Repositories tab and Current variants and the picker are deleted.

Skills: `emil-design-eng`. `emil-animations` was skipped because no motion carries meaning: rail
states are content changes, and the only transition is the tasks chevron's 150ms rotation.
`emil-mobile-native` was skipped because the brief says desk only.

## Layout

| Decision | Reason |
|---|---|
| Two columns (main + a sticky 360px rail) only when the **content area** is at least 1100px, using a container query. Below that the rail stacks **above** the main column. | The canvas table needs ~820px. A viewport breakpoint can't tell whether the sidebar is open, and a container query can. Stacking on top keeps the verdict and Merge where today's action row is: near the top, not below a 40-row table. |
| In the DOM, the rail comes before the main column; in the wide layout it's placed in column 2. | Keyboard and screen-reader users reach the verdict and Merge before the evidence, which is the order in which the page is used. The trade-off is that on wide screens the tab order runs right then left. |
| The attributes card is unchanged (Name, Sync with Git, Schema differs, Last rebase). | The IFC-3200 canvas keeps it untouched. `origin_branch` and `created_at` stay hidden, as today. |
| Branch actions (Propose change, Rebase, Validate, Copy branch name, Go to Tasks and Proposed changes, Delete) move into one **"Actions ▾"** menu in the page header. | This is the `ObjectDetailsMenu` pattern (`object-details-menu.tsx:69`): same button, sections "Actions / Go to / Manage", Delete in red and last. Every detail page then has its actions in the same place, and Merge is the only prominent action. A full-width "Branch actions" dropdown in the rail was tried and rejected (user feedback): it competed with Merge and matched nothing else in the app. |

## Git repositories card (IFC-3200 canvas, section 4)

| Decision | Reason |
|---|---|
| Columns follow the canvas: `Repository · Git state · Commit · Upstream · Last import · ⋮`. | Brief #7. IFC-3200 is building this card, and this design extends it rather than forking it. |
| `Upstream` and `Last import` are hidden, not shown as dashes, until IFC-3146/3147 land (`?upstream=0`). | IFC-3200 says the rows must render without them. Hiding them avoids a column that is blank for every repo. |
| Git state comes from `sync_status` only. The pill colour comes from the dropdown's own colour. | IFC-3199 and IFC-3200: a task can succeed while the import failed. Dropdown colours are schema data, so they aren't hard-coded in the UI. |
| Paging: 10 rows per page with a fixed-height table (`(10+1)×40px` once there is more than one page) and prev/next plus page numbers, with the position in the URL (`repos_page`). | This reuses IFC-3130's `TablePagination`, copied verbatim into the prototype because it isn't on this branch yet. It matches the repository page's Branches card. The fixed height stops the pager jumping on a short last page (user feedback). |
| Failing repositories sort first. | A repo in Import Error on page 3 would be invisible. In the real card this must be server-side ordering, not a client sort. |
| One red band per import error below the table. After 3 bands (`?bands=`), a summary line lists the rest, with "Show all". | Canvas 4c keeps one band per failure because the causes differ. It leaves stacked-versus-summary for 4–5 failures as an open question, so this answers it with "stack 3, then summarise". The number is on a control for the team to set. |
| Generator and artifact problems get their own **amber** bands (blue while running), labelled "Latest task run on this branch. It doesn't block the merge." | Brief #8 keeps generators in scope. They can't be a canvas column without changing Wim's table, and a distinct colour and label keep "import error, blocks" separate from "task result, warns". |
| A reload button in the card header, labelled "Updated <time>", refreshes the card and the rail together. It spins while refreshing and announces "Refreshing…" via `aria-live`. | User request. The card and the rail must never disagree, so one control refreshes both. It's an `@infrahub/ui` `Button` with `aria-label`, not the shared `Retry`, which is a clickable `<div>` with no keyboard access or label (a system gap). |
| Empty state: "Not synchronised with Git" with a one-line reason. The card stays in place. | Canvas 4d, IFC-3200. |
| No permission: a lock and "You don't have access to this branch's repositories". Readiness becomes *unknown*, never clear. | IFC-3104 denies the query rather than trimming rows, and the brief says unknown is never shown as green. |
| Loading: three skeleton rows at the real row height. | The skeleton holds the card's shape so the layout doesn't shift. |

## Merge rail

| State | What it shows | Merge button |
|---|---|---|
| Checking | Spinner, "Checking repositories…" | Disabled |
| Clear | "Ready to merge" on a **plain white** panel | Green **Merge** |
| Clear, no repos | "No Git repositories on this branch" in neutral | Green **Merge** |
| Warn: failed | Amber, "Generator runs failed on this branch", issue list, checkbox "Merge anyway. Artifacts on the default branch may be stale." | Orange **Merge anyway**, enabled only once the box is ticked |
| Warn: running | Blue, "Tasks are still running", checkbox "Merge before these runs finish." | Same |
| Warn: unknown | Neutral, "Couldn't check everything", checkbox "Merge without checking." | Same |
| **Blocked** | Red, "Merge blocked", one row per failed import linked to its band, other warnings listed under "Also on this branch", the reason "Fix the import and wait for it to finish, then merge", and the checkbox "I understand. Merge anyway and carry the failed import into the default branch." | Outline **🔒 Merge**, disabled but focusable, with `aria-describedby` pointing at the reason. Once the box is ticked, it becomes a red (`danger`) **Merge anyway**. |

| Decision | Reason |
|---|---|
| An import error blocks by default and can be overridden with an explicit "I understand" (brief #3, revised twice). | The user asked for the override. A red `danger` button after the override makes "you are merging a broken import" as loud as it can be without forbidding it. |
| The checkbox resets whenever the set of issues changes (the panel is re-keyed on issue keys). | An acknowledgement given for "1 failed generator" must not silently cover a new import error that lands afterwards. |
| A clear state is **not tinted**: white panel, small green check. | An always-green block becomes wallpaper, and then the red and amber panels stop standing out. |
| The disabled blocked button is outline with a lock, not faded green. | Faded green still read as clickable in review. |
| The copy names the consequence ("carry the failed import into the default branch", "artifacts may be stale"), not the mechanism. | The person merging decides on the outcome, not on the task name. |
| Blocking is UI-only (noted in the brief). | A direct `BranchMerge` via API or SDK bypasses it until INFP-670 adds a backend gate. |

## Tasks

| Decision | Reason |
|---|---|
| The tiny "Tasks" accordion becomes a **Branch tasks** card. Its header is a full-width button with an icon, a count and "Latest: <title> <state> <time>" while collapsed, a rotating chevron, and an "All tasks ↗" link. | User feedback: the old accordion was easy to miss. The collapsed header now carries the latest result, so it's useful without being opened. `aria-expanded`/`aria-controls` are wired, and the chevron has no transition under reduced motion. |
| The branch task workflows are unchanged (validate, merge, rebase). Repository tasks live in the Git repositories card. | IFC-3200 keeps the task accordion out of scope. This design only changes how visible it is. |

## Known deviations from the real implementation

- Readiness is computed in the frontend from mocked data (brief #5). A backend readiness query is the follow-up.
- Colours for the Commit and Upstream tints (`#e9f7fa`, `#f4eefa`) and the Git state pills are hard-coded from the canvas. The real card should take the pills from the dropdown's colour and the tints from design tokens.
- `TablePagination` is a copy. Delete it once IFC-3130 merges.

## Round 2 (user feedback, 2026-09-23)

The prototype now has **two variants** behind the picker (`?variant=consistent|legacy`). Both share
the IFC-3200 repositories card, the merge gate logic (`merge-rail.tsx`), and the locate behaviour.

| Decision | Reason |
|---|---|
| **Consistent**: Tasks become a paginated table (10 per page, fixed height, `tasks_page` in the URL) with the same header, row height and pager as the repositories table. Columns: Title, State, Workflow, Related, Updated. Each row expands to show its logs. | User request: one table pattern for every list on the page. The columns mirror `TaskItems` (`entities/tasks/ui/task-items.tsx`), and the table covers branch tasks plus repository tasks. |
| **Legacy**: today's page shape. Attributes card, repositories card, a merge banner **above the familiar button row** (Merge, Propose change, Rebase, Validate, Delete), and the Tasks accordion of cards with nested Logs accordions. | User request: a direction that changes as little of today's UI as possible. The merge gate sits next to the existing buttons instead of in a rail. |
| The amber and blue task bands under the repositories table are **removed**. The card holds only the canvas table plus the import-error bands. Generator and artifact problems live in the task list, and the summary links to them. | User feedback: the summary looked like a duplicate of the tasks. One home per fact: import errors in the repositories card, task results in the task list. |
| The summary becomes **one line per issue** (name + one-line cause + "Show ↓"). There are no messages in it, only the verdict, the links and the gate. | It stays useful as an index ("interesting", per the user) without repeating the detail that sits below. |
| **Locate**: clicking a summary line (or "View task log ↓" on a band) reveals the target, then scrolls to it, moves focus onto it and highlights it for 1.6s. Reveal means switching to the right page, expanding collapsed bands, opening the Tasks accordion, or expanding that row's logs. The highlight is a focus-colour outline plus a 6% tint, fading over 250ms `ease-out`. | Fixes the bug the user reported: the old `#anchor` links didn't reach bands hidden behind "Show all", rows on another page, or collapsed logs. It was checked on all 14 targets in both variants. `emil-animations`: smooth scroll only for pointer activation, instant for keyboard and reduced motion, and a sub-300ms fade. |
| "View task log" on a band now goes to the task row on the same page, not to `/tasks`. "Open in Tasks ↗" in the table header is the way out to the full Tasks page. | You read the log without leaving the page you're merging from. |
| The "You're working on this branch" notice is restored above the header. | It's on today's page and in the canvas. It had been dropped by mistake in round 1. |

System gaps found this round: the shared `Accordion` toggle is a clickable `<div>` (no keyboard
access or button role), as is the shared `Retry`.

## Round 3: "Object layout" variant (user feedback, 2026-09-23)

A third variant (`?variant=object`) uses the object details page's layers and colours exactly, so
the branch page reads like every other detail page. The reference is a Continent object on the
demo instance, plus `pages/objects/object-details-page.tsx` and
`entities/nodes/object/ui/object-details/*`.

| Layer | Object page | Branch page (Object layout) |
|---|---|---|
| Page | `Content.Card` | same |
| Header | `HeaderContainer` row: title, copy, metadata, then `RefreshButton`, Edit, Schema and "Actions ▾" on the right | title, `CopyToClipboardButton`, then the real **`RefreshButton`** and "Actions ▾" (`BranchActionsMenu`, same sections as `ObjectDetailsMenu`) |
| Tabs | `LinkTab` row (`px-4 gap-4`) above the body | same tab styling |
| Body | `Col p-1` with `Card className="to-neutral-50"` | same |
| Content | `DetailsLayout`: Main (2/3) + Aside (1/3) from `xl` | Main: **Details**, **Git repositories** and **Tasks** cards. Aside: **Merge** card |
| Cards | `Card` + `CardHeader` strip (neutral gradient); Details rows use a `200px` label column with `divide-y` | same; the Details rows copy `ObjectDataRow` |

| Decision | Reason |
|---|---|
| The merge panel becomes a normal aside **card** titled "Merge", like Groups and Activities. Only the verdict block inside it is tinted. | Cards on this page are neutral chrome, and colour carries state only. An entirely red card was the "inconsistent layers" the user flagged. |
| The aside is `xl:sticky`. | This is the one deviation from the object page. Merge has to stay visible next to a 40-row table, and the object page's asides (Groups, Activities) don't have that job. |
| Card-header count badges use `Badge variant="blue"` rounded, as the object tabs do. The in-card refresh is dropped in favour of the page-level `RefreshButton`. | One refresh control per page, in the same place as on object pages. |
| **Revised (user):** the Details card keeps today's compact attributes grid (icon + label, four rows: Name, Sync with Git, Schema differs, Last rebase) inside an object-style `Card` + `CardHeader "Details"`. | Full-width `ObjectDataRow`-style rows cost ~290px of height before the repositories. The compact grid keeps today's content and density and adopts only the card chrome, for about 150px. |

## History (skill update, 2026-09-23)

The run now follows the skill's history model.

- **Two axes:** `?variant=consistent|legacy|object` and `?rev=N`. A bare link opens the latest
  revision; any older revision shows the orange "not the current design" banner.
- **Frozen revisions:** `revs/rev-01/` and `revs/rev-02/` are full copies of the prototype. No
  revision imports from another. Object layout has rev 1 (full-width `ObjectDataRow` details) and
  rev 2 (compact attributes in an object card). Consistent and Legacy start at rev 1.
- **Panel:** the skill's `design-history-panel.tsx` + `design-annotations.tsx`. Knobs replace the
  old control panel: scenario, repositories, error bands, rail width, upstream. Notes are scoped to
  `branch-details-repos:<variant>:rev<N>`. There is Copy (clipboard markdown) and Save.
- **Save:** `dev/vite-plugin-design-jam.ts`, registered in `vite.config.ts` with
  `apply: "serve"` and `root: "../../.design"`, writes `feedback.md` and `knobs.json` here.
  Verified: POST returned 204 and wrote to this folder, and the smoke-test files were deleted.
- **One adaptation to the panel:** `frame` pins the fixed shell to the app's content area
  instead of the whole window, so the real sidebar and top bar stay visible and the design keeps
  its true width.
- **Reasoning over time:** `git log -p .design/branch-details-repos/`. **Change as code:**
  `git diff <sha1>..<sha2> -- frontend/app/src/pages/_proto/`.

**History lost before this change, stated plainly:** the phase-2 variants (Current, Checkpoint,
Readiness rail, Repositories tab) and the first refined rail were deleted during phase 3, before
the skill had the "nothing is deleted" rule. They were never committed. Their reasoning survives
in `02-directions.md` and in the earlier sections of this file, but the code does not.

## Round 4 (skill update + user feedback, 2026-09-23)

| Decision | Reason |
|---|---|
| New **Current** variant (`?variant=current`): today's branch details page with none of this design's changes. It uses the real `BranchAttributes` and task badges; the buttons and the task list are static replicas. | User request: a baseline to compare every direction against. The real buttons call the backend (Merge would send a merge request), so they are replicas. |
| Prototype order is **Current, Legacy, Consistent, Object layout**. | User request. It reads as "today, then least to most change". |
| Knobs now belong to each direction. Current has none. Legacy and Object layout have scenario, repositories, bands and upstream. Consistent adds rail width. | The skill's panel now supports per-variant knobs. A control that does nothing in a direction reads as a broken prototype. |
| The panel is pinned to the route's own box, not its parent. | User feedback, "there is no header in the app": the parent includes the app's top bar, so the panel covered it. The panel now starts at y=54, below the top bar. |
| Panel and annotations re-copied from the skill: an armed pin tool catches `pointerdown`, so pinning a button records a note without pressing it (verified on the Actions menu). Sent notes stay visible. | Skill update. The copied files go through the formatter only, never `biome check --write`: its class-sorting fix trims the leading spaces in the pin's class string. |

**URL change (skill update, 2026-09-24):** the panel's parameters are now namespaced:
`?dj.variant=`, `?dj.rev=`, `?dj.compare=`, `?dj.k.<knob>=`. The old `?variant=` / `?rev=` links
open on the default view. The "not the latest" warning is now a floating pill that clears the app's
top bar.

## Round 5 (data availability + round-1 note, 2026-09-29)

Checked against `ple-git-status-header-ifc-3199` (develop base) and its `schema/schema.graphql`.
New revisions: Legacy rev 2, Consistent rev 2, Object layout rev 3, all from `revs/rev-03/`.

| Decision | Reason |
|---|---|
| **Addressed:** Legacy moves Merge into the readiness card, next to the acknowledgement. The card is always shown, including when the branch is clear. The button row keeps Propose change, Rebase, Validate and Delete. | Round-1 note on Legacy rev 1: "include the merge button in the card above". |
| Upstream column, "N behind" chip and Last import column removed. The Upstream toggle is gone; older revisions still show them. | No backend field. Upstream waits on IFC-3146, IFC-3147 and IFC-3154. Last import has no ticket, and IFC-3104 rules out `updated_at`. |
| Import error band shows the raw last error-level line of the import task's log, in monospace, under "<repo> — import failed". | `TaskError` (message, remediation) is only filled in for webhook tasks. There is no curated title or explanation for repo imports. Better text is IFC-3034. |
| New warning for `operational_status` (error-cred, error-connection, error): a triangle icon on the row, an amber band with "Open repository", and a warn-with-acknowledgement verdict. New scenario "Remote unreachable (warn)". | The field exists on `CoreGenericRepository` and wasn't shown. Infrahub can't fetch commits, so the shown commit may be stale. That warns and doesn't block, as brief #3 does for unknown state. |
| Artifacts issue links to the artifact list filtered by status Error, instead of a task log. | Artifact tasks are tagged with each target, not a definition. There's no single task to link to. The counts come from `CoreArtifact.status`. |
| Footnote "N generator runs aren't linked to a repository" removed. | Every `CoreGeneratorDefinition` has a required `repository`, and generator tasks are tagged with the definition id, so this case can't happen. |

Kept, because it can be fetched: repo name, kind, `commit`, `sync_status`. Repo tasks through
`InfrahubTask(related_node__ids: [repoId])`. Generator failed/total from `CoreGeneratorInstance.status`
per definition. Running tasks through `InfrahubTaskBranchStatus`. The merge gate itself is derived
in the frontend; no backend field exists (INFP-670).

## Round 6 (Object layout rev 3 notes, 2026-09-29)

New revision: Object layout rev 4 (`revs/rev-04/`). Legacy and Consistent are unchanged.

| Note | Decision | Reason |
|---|---|---|
| 1. "Remove this card, merge are not blocked, reuse the initial legacy layout having inline buttons … below repositories table" | **Addressed.** The Merge aside is gone and Details, repositories and tasks take the full width. Today's inline buttons (Merge, Propose change, Rebase, Validate, Delete) sit below the repositories table. Merge is a plain button with no gate. The header's Actions menu was removed because it duplicated the buttons. | The owner's call: merges aren't blocked. **This revises brief #3 for this direction.** Import errors and failed generators still show in the repository bands and the Tasks table, but they no longer gate the button. |
| 2. "tasks are not collapsible anymore, just a link to directly the details page of the task" | **Addressed.** The expand column and inline logs are removed, and the title links to `/tasks/<id>`. The band's "View task log →" goes to the same page. | The task details page already shows the logs, so a second log view isn't needed. The mocked ids don't exist on the backend, so the links land on an empty task page. |
| 3. "we can see the white background behind, we should not" | **Addressed.** The panel shell painted `Canvas` (white) behind the page; the harness now passes `background: transparent` in `frame`, so the app's stone-100 shows through as on real pages. The banner uses the real `BranchWorkingNotice` classes (cyan tint, branch icon). | The white came from the design-jam shell, not the design. Fixed in `index.tsx` rather than the copied panel, so it survives skill reloads. It applies to every variant. |
