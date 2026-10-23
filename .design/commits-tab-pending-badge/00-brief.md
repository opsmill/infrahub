# Commits tab: pending-commits badge

## Skipped passes

- Product framing (`emil-product-thinking`) skipped: the user asked straight for prototypes.
- Grilling (`grilling-ideas`) skipped: the idea is already written down in
  [IFC-3467](https://opsmill.atlassian.net/browse/IFC-3467) and
  [IFC-3472](https://opsmill.atlassian.net/browse/IFC-3472), and the user settled the open
  points in the session of 2026-10-20 to 2026-10-23. The answers below are carried from there.

## The problem

The repository page has a Commits tab. Its badge shows the number of commits that are not yet
in use on the current branch: "pending import" on a branch that syncs with Git, "not on this
branch" on a branch that only a rebase updates. It uses the same grey count as the other tabs
(Queries 0, Checks 0), where the number means "how many items this tab lists". On the Commits
tab it does not: "Commits 0" sits next to a list of 14 commits.

The user found this confusing on the demo data (session of 2026-10-22: "the tab count is 0 …
it doesn't look normal"). A total count was tried and then reverted by the user
(2026-10-23): the badge keeps counting pending commits, **but the UI must be different** from
the other tabs' counts.

## Done looks like

Someone glancing at the tab bar can tell, without opening the tab, whether this branch is
missing commits from Git, how many, and whether that is "an import will bring them" or "only
a rebase will bring them" — and nobody reads the badge as the number of commits in the tab.

## Who hits this, and what they were doing before

A network or automation engineer on a repository's page (Integrations → Git Repositories →
a repository), usually checking whether the commit their generators, checks and transforms run
is the latest one, or why a change they pushed to Git is not visible on their Infrahub branch.

## Riskiest assumption

That a badge in the tab bar can carry this meaning at all. If people only look at the badge as
"a number on a tab", any count there will be read as an item count, and the signal has to move
somewhere else (into the tab's label, an icon, or only inside the tab).

## Where it's used

Desk. Infrahub is used in a desktop browser; no touch pass is needed.

## Scenarios every direction must render

The count comes from `pending_count` (worker count under `BEHIND`) and is 0 under `IN_SYNC`;
other conditions have no count. Read-write repositories import on every sync; read-only ones
only when someone starts the import.

There are two kinds of count, never both on one tab (see `03-decisions.md`): **pending import**
(an import brings the commits) and **behind main** (only a rebase in Infrahub brings them; the
wording follows Git's "Your branch is behind 'main' by 2 commits" and names the tracked ref).

| # | Situation | Count today |
|---|---|---|
| **A** | **Read-write repository, branch syncs with Git** | |
| A1 | 3 commits not imported yet (`BEHIND`) | 3 pending import |
| A2 | Nothing pending (`IN_SYNC`) | 0 |
| A3 | 1,284 commits not imported yet (`BEHIND`) | 1284 pending import |
| A4 | Remote branch history rewritten (`REWRITTEN`) | no count |
| A5 | Imported commit missing from the remote (`ORPHANED`) | no count |
| A6 | No remote branch with this name (`NO_REMOTE`) | no count |
| **B** | **Read-write repository, branch does not sync with Git** | |
| B1 | 2 commits behind main (`BEHIND`) | 2 behind main |
| B2 | Up to date with main (`IN_SYNC`) | 0 |
| B3 | 1,284 commits behind main (`BEHIND`) | 1284 behind main |
| B4 | Diverged from main: main's history was rewritten (`REWRITTEN`) | no count |
| B5 | 3 commits newer on the remote main: 2 already imported on main, 1 not imported on main yet (`BEHIND`) | 3 behind main (the API cannot split them) |
| B6 | No commit of its own on this branch (`NOT_TRACKED`) | no count |
| **C** | **Repository added on this branch (`staging`)** | |
| C1 | 1 commit waiting for the next sync | 1 pending import |
| C2 | Nothing pending | 0 |
| **D** | **Read-only repository** | |
| D1 | 2 new commits waiting for a manual import (`BEHIND`) | 2 pending import |
| D2 | Nothing pending | 0 |
| D3 | Tracked branch or tag deleted on the remote (`REF_MISSING`) | no count |
| **E** | **No answer from the commit log** | |
| E1 | First load in progress | spinner |
| E2 | No worker holds a copy yet (`NOT_CLONED`), retrying | no count |
| E3 | Request failed | no count |
| **F** | **Layout** | |
| F1 | Tab bar limited to 900px, Commits partly scrolled away, data of B1 | 2 behind main |
| F2 | Same, data of A3 | 1284 pending import |

The demo repository page already pushes Commits partly out of view at 1200px.

## Out of scope

- The total number of commits (tried and reverted, 2026-10-23).
- The content of the Commits tab itself (header line, row badges, notices): those are in
  [opsmill/infrahub#11189](https://github.com/opsmill/infrahub/pull/11189).
- Any backend change. `pending_count` and `condition` already exist.
- Other tabs' counts.
