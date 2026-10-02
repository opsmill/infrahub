# 04 — Review (Object layout)

Reviewed: Object layout rev 5 → fixes shipped as **rev 6**
(`?dj.variant=object&dj.rev=6`), 2026-09-29. Every finding is fixed or accepted with a reason.

## 4a — Tidy (ui-polish, surfaces)

| Finding | Outcome |
|---|---|
| Repository row "⋯" menu buttons are 28×28 in 40px rows. | **Fixed:** a pseudo-element extends them to 40×40. The row is 40px, so the hit area doesn't overlap its neighbours. |
| Task title links are 17px-tall text inside 40px rows. | **Fixed:** the link fills the cell (`block leading-10`), so the whole title cell is the target (40px). |
| "Open in Tasks" is 18px tall. | **Fixed:** the hit area is extended vertically, within the card header. |
| Merge's trailing check icon uses symmetric padding. | **Accepted:** it's the app's `Button` as used on today's page. Optical padding belongs to the design system, not this screen. |
| Surfaces: body card → cards → error bands. | **No change:** same layers as the object details page. Bands sit inside `overflow-hidden` cards, so their corners follow the card radius. |
| White shell behind the page (round 6 note). | Already fixed in rev 4 (the shell is transparent). |
| Numbers: counts, commits, pagination. | **No change:** already `tabular-nums`; body is antialiased. |

## 4b — Critique (ui-review)

| Finding | Outcome |
|---|---|
| The header lost the branch description that today's page shows under the title. | **Fixed:** the description is shown under the title, as on today's page. |
| No branch status next to the title (today: `BranchStatusBadge`). | **Fixed:** uses the real `BranchStatusBadge`. It renders nothing for an open branch, as today, and shows "Rebase needed", "Rebase needed (upgrade)", "Deleting" or "Merged"; any other status (`MERGE_FAILED` included) renders nothing. *(Corrected 2026-10-02: this said "Need rebase / Merging", labels the badge doesn't have.)* |
| "Name" in Details repeats the title. | **Accepted:** the brief keeps today's attribute card unchanged. |
| Hierarchy: errors (bands) → Merge → tasks. | **No change:** the owner asked for the buttons below the repositories (round 6), and a problem is read before the button that ignores it. |

## 4c — Readiness (prep-for-prod)

Marketing and SEO lanes skipped: internal screen.

| Finding | Outcome |
|---|---|
| Loading: the Tasks card showed an empty table with a "0" count. | **Fixed:** skeleton rows, and no count until loaded. |
| No repository permission (`denied`): the Tasks card was empty. | **Fixed:** branch tasks (validate, rebase) still show. Only repository-linked tasks are hidden, because the permission is on repositories. |
| No tasks at all rendered a bare table header. | **Fixed:** an empty state explains what appears there. |
| Dark mode. | **Accepted:** the design branch has no theme support, so the prototype can't be checked in dark mode. The implementation base (`cross-branch-repo-status-infp-671`) has the theme: the implementation uses its tokens and is checked in both themes. |
| `console.log`, lorem, div-buttons. | None found. |

## 4d — By hand

| Check | Result |
|---|---|
| Tab from the top | Refresh → tabs → each repository and its ⋯ → View task log → Merge, Propose change, Rebase, Validate, Delete → Open in Tasks → task links. Order matches the layout. The first stop, the app's `CopyToClipboardButton`, has **no accessible name**. **Accepted** here as a system gap (shared component), listed in the handoff. |
| Focus ring | Visible on every stop (app `Button` ring, default outline on links). |
| Phone width (390px) | The pane scrolls sideways: the tab row and the 560px tables overflow. **Accepted:** the brief is desktop-only ("desk only"), and today's tab row does the same. |
| Every state still renders | incident, import error, failed generator, remote unreachable, running, 40 repos / 5 errors (both tables paginate), tasks unknown, all clear, no Git counterpart, loading, no permission: all render with no console errors from the page. The two remaining errors are the missing shared-notes schema. |

Screenshots: automated capture is unreliable in this browser session (frames stop when the window
is hidden), so the handoff screenshots are taken in Phase 5 with the window in front.

**The gate is clean.**
